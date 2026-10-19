"""
질문 처리 파이프라인 — 워크시트 '2. 처리하는 곳'의 순서 그대로 실행한다.

  입력 필터 → 의도 분류 → 기간 해석 → SQL 생성(템플릿 우선, 없으면 LLM)
  → SQL 검증 → 읽기전용 실행 → 결과 마스킹 → 차트 추천/요약

각 단계의 결과를 steps 에 남겨서 화면의 '처리 단계' 탭에 그대로 보여준다
(어느 단계에서 왜 막혔는지 사용자가 확인할 수 있게).
"""
from __future__ import annotations

import re
import sqlite3
import time
from datetime import date

from app.database.sqlite_client import QueryTimeout, ReadOnlyViolation, execute_select
from app.pipeline import chart, injection_filter, intent_router, llm_sql, templates
from app.pipeline.date_parser import parse_date_range
from app.pipeline.sql_validator import validate_sql
from app.utils.masking import mask_rows


_COUNTRY_WORDS = {
    "KR": ("한국", "국내", "kr"),
    "JP": ("일본", "jp"),
    "TW": ("대만", "tw"),
}


def detect_country(question: str) -> str | None:
    """질문에 국가가 하나만 언급되면 그 국가 코드. ('kr' 은 단어 경계로만 매칭)"""
    q = (question or "").lower()
    found = set()
    for code, words in _COUNTRY_WORDS.items():
        for w in words:
            if w.isascii():
                if re.search(rf"(?<![a-z]){w}(?![a-z])", q):
                    found.add(code)
            elif w in q:
                found.add(code)
    return found.pop() if len(found) == 1 else None


class _Trace:
    def __init__(self) -> None:
        self.steps: list[dict] = []
        self._t = time.perf_counter()

    def add(self, key: str, label: str, status: str, detail: str = "") -> None:
        now = time.perf_counter()
        self.steps.append({"key": key, "label": label, "status": status, "detail": detail,
                           "ms": int((now - self._t) * 1000)})
        self._t = now


def run_query(question: str, country: str = "ALL", today: date | None = None) -> dict:
    started = time.perf_counter()
    today = today or date.today()
    trace = _Trace()
    result: dict = {
        "question": question, "country": country, "intent": None, "status": "error", "message": None,
        "sql_source": None, "template": None, "date_range": None, "sql": None,
        "columns": [], "rows": [], "row_count": 0, "truncated": False,
        "chart": None, "summary": [], "masked_count": 0, "warnings": [], "llm": None,
    }

    def finish(status: str, message: str | None = None) -> dict:
        result["status"] = status
        result["message"] = message
        result["steps"] = trace.steps
        result["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        return result

    # 1) 입력 필터
    hit = injection_filter.detect_injection(question)
    if hit:
        trace.add("filter", "입력 필터", "blocked", "프롬프트 인젝션/데이터 변경 의심 패턴")
        return finish("blocked", "보안 정책상 처리할 수 없는 질문입니다 (데이터 변경·지시 무시 등 의심 패턴 감지).")
    category = injection_filter.detect_sensitive_request(question)
    if category:
        trace.add("filter", "입력 필터", "blocked", f"민감 개인정보 요청: {category}")
        return finish("blocked", f"'{category}' 같은 민감 개인정보는 조회할 수 없습니다. 집계(건수·비율) 형태로 질문해 주세요.")
    trace.add("filter", "입력 필터", "ok", "인젝션·민감정보 요청 없음")

    # 2) 의도 분류
    intent = intent_router.classify_intent(question)
    result["intent"] = intent
    if intent != "sql":
        trace.add("intent", "의도 분류", "ok", "날씨 질문" if intent == "weather" else "일상 대화")
        return finish("chat", intent_router.chat_reply(question, intent))
    # 화면에서 '전체'를 골랐어도 질문에 국가가 하나 있으면 그 국가로 조회 ("JP 지난주 매출")
    mentioned = detect_country(question)
    if country == "ALL" and mentioned:
        country = mentioned
        result["country"] = country
        trace.add("intent", "의도 분류", "ok", f"데이터 질문 (질문에서 국가 {country} 인식)")
    else:
        trace.add("intent", "의도 분류", "ok", "데이터 질문")

    # 3) 기간 해석
    dr = parse_date_range(question, today)
    result["date_range"] = dr.to_dict() if dr else None
    trace.add("period", "기간 해석", "ok" if dr else "info",
              f"{dr.label} ({dr.start} ~ {dr.end})" if dr else "기간 표현 없음 → 전체 기간")

    # 4) SQL 생성 — 템플릿 우선
    tpl = templates.resolve_template(question, country, today)
    if tpl:
        result["sql_source"] = "template"
        result["template"] = {"name": tpl.name, "title": tpl.title, "notes": tpl.notes}
        raw_sql = tpl.sql
        trace.add("generate", "SQL 생성", "ok", f"템플릿 사용: {tpl.title}")
    else:
        gen = llm_sql.generate_sql(question, country, dr, today)
        result["llm"] = {"model": gen.model, "latency_ms": gen.latency_ms,
                         "input_tokens": gen.input_tokens, "output_tokens": gen.output_tokens}
        if not gen.sql:
            trace.add("generate", "SQL 생성", "error", gen.error or "SQL 생성 실패")
            msg = gen.error or "SQL 을 만들지 못했습니다."
            if gen.error and gen.error.startswith("LLM 미연결"):
                msg = ("이 질문은 아직 템플릿이 없어서 LLM 이 필요합니다. 현재 LLM 이 연결되지 않은 상태라 "
                       "예시 질문(매출·가입자·탈퇴·작품/업체 순위·DAU/MAU)으로 시도해 주세요.")
            return finish("error", msg)
        result["sql_source"] = "llm"
        raw_sql = gen.sql
        trace.add("generate", "SQL 생성", "ok", f"LLM 생성 ({gen.model}, {gen.latency_ms:,}ms)")

    # 5) SQL 검증
    v = validate_sql(raw_sql)
    result["sql"] = v.sql
    if not v.ok:
        trace.add("validate", "SQL 검증", "blocked", " / ".join(v.errors))
        return finish("blocked", "생성된 SQL 이 안전 규칙에 맞지 않아 실행하지 않았습니다: " + " / ".join(v.errors))
    result["warnings"].extend(v.warnings)
    trace.add("validate", "SQL 검증", "ok", f"SELECT 단일문, 테이블 {', '.join(v.tables)}")

    # 6) 읽기전용 실행
    try:
        qr = execute_select(v.sql)
    except ReadOnlyViolation as e:
        trace.add("execute", "읽기전용 실행", "blocked", str(e))
        return finish("blocked", str(e))
    except QueryTimeout as e:
        trace.add("execute", "읽기전용 실행", "error", str(e))
        return finish("error", f"{e}. 기간을 좁혀서 다시 질문해 주세요.")
    except sqlite3.Error as e:
        trace.add("execute", "읽기전용 실행", "error", f"DB 오류: {e}")
        return finish("error", f"SQL 실행 중 오류가 발생했습니다: {e}")
    result["warnings"].extend(qr.warnings)
    trace.add("execute", "읽기전용 실행", "ok", f"{len(qr.rows):,}행, {qr.elapsed_ms:,}ms")

    # 7) 결과 마스킹
    rows, masked = mask_rows(qr.rows)
    result["masked_count"] = masked
    trace.add("mask", "결과 마스킹", "ok", f"개인정보 {masked}건 마스킹" if masked else "마스킹 대상 없음")

    # 8) 차트 추천 / 요약
    result["columns"] = qr.columns
    result["rows"] = rows
    result["row_count"] = len(rows)
    result["truncated"] = qr.truncated
    result["chart"] = chart.recommend_chart(question, qr.columns, rows)
    result["summary"] = chart.summary_cards(qr.columns, rows)
    trace.add("chart", "차트 추천", "ok" if result["chart"] else "info",
              f"{result['chart']['type']} 차트" if result["chart"] else "차트 없이 표로 표시")

    return finish("success", None if rows else "조건에 맞는 데이터가 없습니다.")
