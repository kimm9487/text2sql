"""
LLM SQL 생성 — 템플릿이 없는 질문은 Claude 가 SQL 을 작성한다.

중간 단계 구현
  - 스키마 전체(테이블 7개)를 프롬프트에 넣는 방식
  - .env 의 LLM_PROVIDER=claude + ANTHROPIC_API_KEY 가 있을 때만 동작 (없으면 템플릿 질문만 처리)
기말 예정
  - RAG: 스키마 설명 + 관리자가 등록한 '검증된 정답 쿼리'를 벡터DB 에서 검색해 프롬프트에 넣기
  - 실패 시 오류 메시지를 넣고 1회 자동 재생성
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date

from app.config import settings
from app.database.schema_info import schema_prompt_text
from app.pipeline.date_parser import DateRange

SYSTEM_PROMPT = """너는 웹소설 플랫폼 데이터 분석용 SQLite SQL 을 작성하는 도우미다.
사용자의 한국어 질문을 아래 스키마에 맞는 SQLite SELECT 문 하나로 바꾼다.

규칙
1. SELECT (또는 WITH ... SELECT) 한 문장만 작성한다. 데이터 변경 구문은 절대 쓰지 않는다.
2. 스키마에 있는 테이블·컬럼만 쓴다. 없는 컬럼을 지어내지 않는다.
3. password_hash 는 절대 조회하지 않는다. 이름·이메일·전화번호는 질문이 목록을 요구할 때만 쓰고, members 는 SELECT * 금지.
4. 결과 컬럼에는 한국어 별칭을 붙인다. 예: SUM(p.amount) AS 매출
5. 플랫폼 매출은 payments 에서 status = 'paid' 인 amount 합계다.
   작품·업체·장르별 매출은 coin_usages.coins 합계 × 100 (원) 이다.
6. 날짜는 SQLite 함수(date(), strftime())를 쓴다. 기간 필터는 컬럼을 함수로 감싸지 말고
   col >= '시작일' AND col < '종료일 다음날' 형식으로 쓴다.
7. 시계열은 시간축 오름차순, 순위는 지표 내림차순으로 정렬한다.
8. LIMIT 은 사용자가 개수를 말한 경우에만 붙인다.
9. 답은 ```sql 코드블록 하나만 출력하고 설명은 쓰지 않는다.
   질문이 이 데이터로 답할 수 없는 내용이면 코드블록 대신 'UNANSWERABLE: 이유' 한 줄만 쓴다."""


@dataclass
class LLMSQLResult:
    sql: str | None
    error: str | None
    latency_ms: int
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


_SQL_BLOCK_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)


def extract_sql(text: str) -> str | None:
    m = _SQL_BLOCK_RE.search(text or "")
    if m:
        return m.group(1).strip()
    stripped = (text or "").strip()
    return stripped if stripped.upper().startswith(("SELECT", "WITH")) else None


def build_user_prompt(question: str, country: str, dr: DateRange | None, today: date) -> str:
    country_line = (
        f"선택 국가: {country} → 국가 컬럼이 있는 테이블은 country = '{country}' 조건을 반드시 넣는다."
        if country != "ALL" else "선택 국가: 전체 (국가 조건 없음)"
    )
    period_line = (
        f"코드가 해석한 기간: {dr.label} = {dr.start} ~ {dr.end} (이 기간을 그대로 사용)"
        if dr else "코드가 해석한 기간: 없음 (질문에 기간이 없으면 전체 기간)"
    )
    return (
        f"## 스키마\n{schema_prompt_text()}\n\n"
        f"## 조건\n오늘 날짜: {today.isoformat()}\n{country_line}\n{period_line}\n\n"
        f"## 질문\n{question}"
    )


def generate_sql(question: str, country: str, dr: DateRange | None, today: date | None = None) -> LLMSQLResult:
    model = settings.llm_model
    if not settings.llm_enabled:
        return LLMSQLResult(None, "LLM 미연결 (LLM_PROVIDER=claude 와 ANTHROPIC_API_KEY 설정 필요)", 0, model)

    import anthropic  # LLM 을 안 쓰는 환경에서도 서버가 뜨도록 지연 import

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0)
    started = time.perf_counter()
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(question, country, dr, today or date.today())}],
            output_config={"effort": settings.llm_effort},
            # 안전 분류기가 요청을 거절하면 서버가 대체 모델로 자동 재시도
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        return LLMSQLResult(None, "LLM 인증 실패 (API 키 확인)", _ms(started), model)
    except anthropic.RateLimitError:
        return LLMSQLResult(None, "LLM 호출 한도 초과 — 잠시 후 다시 시도", _ms(started), model)
    except anthropic.APIStatusError as e:
        return LLMSQLResult(None, f"LLM 오류 ({e.status_code})", _ms(started), model)
    except anthropic.APIConnectionError:
        return LLMSQLResult(None, "LLM 서버 연결 실패", _ms(started), model)

    latency = _ms(started)
    usage = response.usage
    tokens = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}

    if response.stop_reason == "refusal":
        return LLMSQLResult(None, "LLM 이 요청을 거절함", latency, response.model, **tokens)

    text = "".join(b.text for b in response.content if b.type == "text")
    if text.strip().upper().startswith("UNANSWERABLE"):
        reason = text.split(":", 1)[1].strip() if ":" in text else "이 데이터로 답할 수 없는 질문"
        return LLMSQLResult(None, f"답할 수 없는 질문: {reason}", latency, response.model, **tokens)

    sql = extract_sql(text)
    if not sql:
        return LLMSQLResult(None, "LLM 응답에서 SQL 을 찾지 못함", latency, response.model, **tokens)
    return LLMSQLResult(sql, None, latency, response.model, **tokens)


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
