"""
결정적 템플릿 — 자주 쓰는 핵심 지표는 LLM 대신 코드가 SQL 을 직접 만든다.

LLM 은 같은 질문에도 매번 다른 SQL 을 낼 수 있고, 없는 컬럼을 지어내거나 기간을 잘못
해석할 수 있다. 매출·가입자처럼 틀리면 보고서에 그대로 옮겨지는 지표는 정의를 코드로 고정한다.

중간 단계 등록 템플릿 (9종)
  1. revenue_total        기간 매출 합계 (결제 완료 기준)
  2. revenue_by_country   국가별 매출
  3. revenue_trend        일별/월별 매출 추이
  4. partner_revenue      파트너사(CP)별 매출 순위 (상위/하위 N)
  5. content_revenue      작품별 매출 순위 (인기 작품 TOP N)
  6. genre_revenue        장르별 매출 비중
  7. new_members          신규 가입자 수 (기간/일별/월별/국가별)
  8. withdrawn_members    탈퇴 회원 수
  9. active_users         DAU / MAU (로그인 기준)
  +  recent_members       최근 가입 회원 목록 (결과 마스킹 확인용)

원칙: 질문에 템플릿이 처리하지 않는 차원(결제수단·성별·작가 등)이 있으면 None 을 돌려
LLM 에 넘긴다. 템플릿으로 억지로 답하면 질문이 요구한 조건이 조용히 빠진 숫자가 나온다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.pipeline.date_parser import DateRange, parse_date_range

COUNTRIES = ("KR", "JP", "TW")
COIN_TO_KRW = 100

_REVENUE_KW = ("매출", "수익", "결제 금액", "결제금액", "결제액", "매상")
_PARTNER_KW = ("파트너", "업체", "cp", "제공사")
_CONTENT_KW = ("작품", "웹소설", "인기")
_GENRE_KW = ("장르",)
_COUNTRY_GROUP_KW = ("국가별", "나라별", "국가 별", "국가마다")
_NEW_MEMBER_KW = ("신규", "가입자", "가입 회원", "가입회원", "가입한 회원", "가입 수", "가입수")
_WITHDRAW_KW = ("탈퇴", "이탈")
_ACTIVE_KW = ("dau", "mau", "활성 사용자", "활성사용자", "활성 회원", "접속자", "방문자", "로그인 회원", "로그인한 회원")
_DAILY_KW = ("일별", "일자별", "날짜별", "매일", "하루")
_MONTHLY_KW = ("월별", "달별", "매월", "월간")
_TREND_KW = ("추이", "추세", "흐름", "그래프", "변화")
_BOTTOM_KW = ("하위", "낮은", "적은", "저조", "꼴찌", "최저")
# 템플릿이 다루지 않는 차원 — 하나라도 있으면 LLM 으로 넘긴다
_UNSUPPORTED_DIM_KW = (
    "결제수단", "결제 수단", "수단별", "성별", "연령", "나이", "기기", "디바이스", "가입경로", "가입 경로",
    "채널", "작가", "시간대", "요일", "환불", "객단가", "arpu", "평균", "휴면", "완결", "연재",
)


@dataclass
class TemplateResult:
    name: str
    title: str
    sql: str
    date_range: DateRange | None
    notes: list[str] = field(default_factory=list)


def _has(q: str, keywords) -> bool:
    return any(k in q for k in keywords)


def _country_cond(alias: str, country: str) -> str:
    # country 는 라우터에서 화이트리스트 검사를 마친 값만 들어온다 (문자열 결합 안전)
    return f"\n  AND {alias}.country = '{country}'" if country in COUNTRIES else ""


def _date_cond(col: str, dr: DateRange | None) -> str:
    # 컬럼을 함수로 감싸지 않는 범위 조건 — 인덱스를 탈 수 있게 (date(col) BETWEEN ... 금지)
    if not dr:
        return ""
    start, end_excl = dr.sql_bounds()
    return f"\n  AND {col} >= '{start}' AND {col} < '{end_excl}'"


def _grain(q: str, dr: DateRange | None) -> str | None:
    """'daily' | 'monthly' | None(기간 합계)."""
    if _has(q, _DAILY_KW):
        return "daily"
    if _has(q, _MONTHLY_KW):
        return "monthly"
    if _has(q, _TREND_KW):
        return "daily" if dr and dr.days <= 62 else "monthly"
    return None


def _bucket(col: str, grain: str) -> tuple[str, str]:
    """(SELECT 식, 별칭)"""
    if grain == "daily":
        return f"date({col})", "일자"
    return f"strftime('%Y-%m', {col})", "월"


def _parse_limit(q: str) -> int | None:
    """개수가 명시된 경우만 LIMIT ('3개월'의 3을 개수로 오인하지 않도록 '개월' 제외)."""
    m = re.search(r"(?:상위|하위|top|탑)\s*(\d{1,3})", q)
    if not m:
        m = re.search(r"(\d{1,3})\s*(?:개(?!월)|위|곳|편)", q)
    return int(m.group(1)) if m else None


# ── 템플릿 빌더 ────────────────────────────────────────────────────────────

def _revenue_total(country: str, dr: DateRange | None) -> str:
    return (
        "SELECT SUM(p.amount) AS 매출,\n"
        "       COUNT(*) AS 결제건수,\n"
        "       COUNT(DISTINCT p.member_id) AS 결제자수\n"
        "FROM payments p\n"
        "WHERE p.status = 'paid'"
        f"{_date_cond('p.paid_at', dr)}{_country_cond('p', country)}"
    )


def _revenue_by_country(country: str, dr: DateRange | None, grain: str | None) -> str:
    if grain:
        expr, alias = _bucket("p.paid_at", grain)
        return (
            f"SELECT {expr} AS {alias},\n"
            "       p.country AS 국가,\n"
            "       SUM(p.amount) AS 매출\n"
            "FROM payments p\n"
            "WHERE p.status = 'paid'"
            f"{_date_cond('p.paid_at', dr)}{_country_cond('p', country)}\n"
            f"GROUP BY {expr}, p.country\n"
            f"ORDER BY {expr}, p.country"
        )
    return (
        "SELECT p.country AS 국가,\n"
        "       SUM(p.amount) AS 매출,\n"
        "       COUNT(*) AS 결제건수,\n"
        "       COUNT(DISTINCT p.member_id) AS 결제자수\n"
        "FROM payments p\n"
        "WHERE p.status = 'paid'"
        f"{_date_cond('p.paid_at', dr)}{_country_cond('p', country)}\n"
        "GROUP BY p.country\n"
        "ORDER BY 매출 DESC"
    )


def _revenue_trend(country: str, dr: DateRange | None, grain: str) -> str:
    expr, alias = _bucket("p.paid_at", grain)
    return (
        f"SELECT {expr} AS {alias},\n"
        "       SUM(p.amount) AS 매출,\n"
        "       COUNT(*) AS 결제건수\n"
        "FROM payments p\n"
        "WHERE p.status = 'paid'"
        f"{_date_cond('p.paid_at', dr)}{_country_cond('p', country)}\n"
        f"GROUP BY {expr}\n"
        f"ORDER BY {expr}"
    )


def _rank_order(q: str) -> str:
    return "ASC" if _has(q, _BOTTOM_KW) else "DESC"


def _partner_revenue(q: str, country: str, dr: DateRange | None) -> str:
    # 업체 매출 = 그 업체 작품에 사용된 코인 × 100원. 매출이 0인 업체도 보이도록 LEFT JOIN.
    limit = _parse_limit(q)
    usage_filter = f"{_date_cond('u.used_at', dr)}{_country_cond('u', country)}".replace("\n  AND", "\n     AND")
    sql = (
        "SELECT pt.partner_name AS 업체명,\n"
        f"       COALESCE(SUM(u.coins), 0) * {COIN_TO_KRW} AS 코인매출,\n"
        "       COUNT(DISTINCT c.content_id) AS 작품수\n"
        "FROM partners pt\n"
        "LEFT JOIN contents c ON c.partner_id = pt.partner_id\n"
        f"LEFT JOIN coin_usages u ON u.content_id = c.content_id{usage_filter}\n"
        "GROUP BY pt.partner_id, pt.partner_name\n"
        f"ORDER BY 코인매출 {_rank_order(q)}"
    )
    return sql + (f"\nLIMIT {limit}" if limit else "")


def _content_revenue(q: str, country: str, dr: DateRange | None) -> str:
    limit = _parse_limit(q)
    if limit is None and _has(q, ("top", "탑", "상위", "하위", "인기", "가장")):
        limit = 10
    sql = (
        "SELECT c.title AS 작품명,\n"
        "       c.genre AS 장르,\n"
        "       pt.partner_name AS 업체명,\n"
        f"       SUM(u.coins) * {COIN_TO_KRW} AS 코인매출,\n"
        "       COUNT(DISTINCT u.member_id) AS 구매자수\n"
        "FROM coin_usages u\n"
        "JOIN contents c ON c.content_id = u.content_id\n"
        "JOIN partners pt ON pt.partner_id = c.partner_id\n"
        "WHERE 1 = 1"
        f"{_date_cond('u.used_at', dr)}{_country_cond('u', country)}\n"
        "GROUP BY c.content_id, c.title, c.genre, pt.partner_name\n"
        f"ORDER BY 코인매출 {_rank_order(q)}"
    )
    return sql + (f"\nLIMIT {limit}" if limit else "")


def _genre_revenue(country: str, dr: DateRange | None) -> str:
    return (
        "SELECT c.genre AS 장르,\n"
        f"       SUM(u.coins) * {COIN_TO_KRW} AS 코인매출,\n"
        "       ROUND(100.0 * SUM(u.coins) / SUM(SUM(u.coins)) OVER (), 1) AS 비중_퍼센트\n"
        "FROM coin_usages u\n"
        "JOIN contents c ON c.content_id = u.content_id\n"
        "WHERE 1 = 1"
        f"{_date_cond('u.used_at', dr)}{_country_cond('u', country)}\n"
        "GROUP BY c.genre\n"
        "ORDER BY 코인매출 DESC"
    )


def _member_count(col: str, label: str, q: str, country: str, dr: DateRange | None,
                  extra_where: str = "") -> str:
    grain = _grain(q, dr)
    group_country = _has(q, _COUNTRY_GROUP_KW)
    selects, groups = [], []
    if grain:
        expr, alias = _bucket(f"m.{col}", grain)
        selects.append(f"{expr} AS {alias}")
        groups.append(expr)
    if group_country:
        selects.append("m.country AS 국가")
        groups.append("m.country")
    selects.append(f"COUNT(*) AS {label}")
    sql = (
        "SELECT " + ",\n       ".join(selects) + "\n"
        "FROM members m\n"
        f"WHERE m.{col} IS NOT NULL{extra_where}"
        f"{_date_cond(f'm.{col}', dr)}{_country_cond('m', country)}"
    )
    if groups:
        order = ", ".join(groups) if grain else f"{label} DESC"
        sql += f"\nGROUP BY {', '.join(groups)}\nORDER BY {order}"
    return sql


def _active_users(q: str, country: str, dr: DateRange | None) -> tuple[str, str]:
    """로그인 기준 활성 사용자. (sql, 제목)"""
    if "mau" in q or _has(q, _MONTHLY_KW):
        grain, title = "monthly", "월간 활성 사용자(MAU)"
    elif "dau" in q or _has(q, _DAILY_KW) or (_has(q, _TREND_KW) and dr and dr.days <= 62):
        grain, title = "daily", "일간 활성 사용자(DAU)"
    elif _has(q, _TREND_KW):
        grain, title = "monthly", "월간 활성 사용자(MAU)"
    else:
        grain, title = None, "기간 내 접속 회원 수"
    where = f"WHERE 1 = 1{_date_cond('l.login_at', dr)}{_country_cond('l', country)}"
    if grain:
        expr, alias = _bucket("l.login_at", grain)
        sql = (
            f"SELECT {expr} AS {alias},\n"
            "       COUNT(DISTINCT l.member_id) AS 활성사용자수\n"
            "FROM login_logs l\n"
            f"{where}\n"
            f"GROUP BY {expr}\n"
            f"ORDER BY {expr}"
        )
    else:
        sql = (
            "SELECT COUNT(DISTINCT l.member_id) AS 접속회원수,\n"
            "       COUNT(*) AS 로그인횟수\n"
            "FROM login_logs l\n"
            f"{where}"
        )
    return sql, title


def _recent_members(q: str, country: str) -> str:
    m = re.search(r"(\d{1,3})\s*명", q)
    n = int(m.group(1)) if m else 10
    return (
        "SELECT m.member_id AS 회원ID, m.name AS 이름, m.email AS 이메일, m.phone AS 전화번호,\n"
        "       m.country AS 국가, m.joined_at AS 가입일시\n"
        "FROM members m\n"
        f"WHERE 1 = 1{_country_cond('m', country)}\n"
        "ORDER BY m.joined_at DESC\n"
        f"LIMIT {min(n, 50)}"
    )


# ── 진입점 ────────────────────────────────────────────────────────────────

def resolve_template(question: str, country: str = "ALL", today: date | None = None) -> TemplateResult | None:
    q = (question or "").lower()
    dr = parse_date_range(question, today)

    # 최근 가입 회원 목록 (개인정보 마스킹 확인용)
    if "회원" in q and _has(q, ("목록", "명단", "리스트")) and _has(q, ("최근", "신규", "가입")):
        return TemplateResult("recent_members", "최근 가입 회원 목록", _recent_members(q, country), None,
                              ["이름·이메일·전화번호는 결과에서 마스킹됨"])

    if _has(q, _UNSUPPORTED_DIM_KW):
        return None

    if _has(q, _WITHDRAW_KW):
        sql = _member_count("withdrawn_at", "탈퇴회원수", q, country, dr)
        return TemplateResult("withdrawn_members", "탈퇴 회원 수", sql, dr,
                              ["탈퇴일시(withdrawn_at) 기준"])

    # '신규 결제자'처럼 결제 조건이 붙으면 가입자 수 템플릿이 아님 → LLM
    if _has(q, _NEW_MEMBER_KW) and not _has(q, _REVENUE_KW + ("결제",)):
        sql = _member_count("joined_at", "신규가입자수", q, country, dr)
        return TemplateResult("new_members", "신규 가입자 수", sql, dr, ["가입일시(joined_at) 기준"])

    if _has(q, _ACTIVE_KW):
        sql, title = _active_users(q, country, dr)
        return TemplateResult("active_users", title, sql, dr, ["로그인 기록 기준, 회원 중복 제거"])

    coin_note = f"작품에 사용된 코인 × {COIN_TO_KRW}원 기준 (결제 금액과는 다를 수 있음)"
    is_revenue = _has(q, _REVENUE_KW)

    rank_words = ("인기", "top", "탑", "순위", "많이 팔린", "비중")

    # 장르를 먼저 본다 ('인기 장르'가 작품 순위로 빠지지 않게)
    if _has(q, _GENRE_KW) and (is_revenue or _has(q, rank_words)):
        return TemplateResult("genre_revenue", "장르별 매출 비중", _genre_revenue(country, dr), dr, [coin_note])
    if _has(q, _PARTNER_KW) and (is_revenue or _has(q, rank_words)):
        return TemplateResult("partner_revenue", "파트너사별 매출 순위", _partner_revenue(q, country, dr), dr,
                              [coin_note])
    if _has(q, _CONTENT_KW) and (is_revenue or _has(q, rank_words)):
        return TemplateResult("content_revenue", "작품별 매출 순위", _content_revenue(q, country, dr), dr,
                              [coin_note])

    if is_revenue:
        pay_note = "결제 완료(status='paid') 금액 기준, 환불 제외"
        grain = _grain(q, dr)
        if _has(q, _COUNTRY_GROUP_KW):
            return TemplateResult("revenue_by_country", "국가별 매출", _revenue_by_country(country, dr, grain), dr,
                                  [pay_note])
        if grain:
            title = "일별 매출 추이" if grain == "daily" else "월별 매출 추이"
            return TemplateResult("revenue_trend", title, _revenue_trend(country, dr, grain), dr, [pay_note])
        return TemplateResult("revenue_total", "기간 매출 합계", _revenue_total(country, dr), dr, [pay_note])

    return None
