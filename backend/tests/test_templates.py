import re

import pytest

from app.pipeline.sql_validator import validate_sql
from app.pipeline.templates import resolve_template
from tests.conftest import TEST_TODAY


@pytest.mark.parametrize("q, name", [
    ("지난달 매출 알려줘", "revenue_total"),
    ("지난달 국가별 매출", "revenue_by_country"),
    ("최근 6개월 월별 매출 추이", "revenue_trend"),
    ("이번달 일별 매출", "revenue_trend"),
    ("매출 하위 5개 파트너사", "partner_revenue"),
    ("업체별 매출", "partner_revenue"),
    ("올해 인기 작품 TOP 5", "content_revenue"),
    ("장르별 매출 비중", "genre_revenue"),
    ("인기 장르", "genre_revenue"),
    ("이번달 신규 가입자 수", "new_members"),
    ("지난달 탈퇴 회원 수", "withdrawn_members"),
    ("최근 30일 DAU 추이", "active_users"),
    ("월별 MAU", "active_users"),
    ("최근 가입한 회원 목록 5명", "recent_members"),
])
def test_routes_to_template(q, name):
    tpl = resolve_template(q, "ALL", TEST_TODAY)
    assert tpl is not None and tpl.name == name


@pytest.mark.parametrize("q", [
    "결제수단별 매출",          # 템플릿이 없는 차원
    "작가별 매출 순위",
    "성별 매출 비교",
    "신규 결제자 수",            # 가입자 템플릿으로 빠지면 안 됨
    "평균 결제 금액",
])
def test_unsupported_dimension_goes_to_llm(q):
    assert resolve_template(q, "ALL", TEST_TODAY) is None


@pytest.mark.parametrize("q", [
    "지난달 국가별 매출", "최근 6개월 월별 매출 추이", "매출 하위 5개 파트너사", "올해 인기 작품 TOP 5",
    "장르별 매출 비중", "이번달 일별 신규 가입자 수", "지난달 국가별 탈퇴 회원 수", "최근 30일 DAU 추이",
    "최근 가입한 회원 목록 5명",
])
@pytest.mark.parametrize("country", ["ALL", "KR", "JP", "TW"])
def test_template_sql_passes_validator(q, country):
    tpl = resolve_template(q, country, TEST_TODAY)
    assert validate_sql(tpl.sql, 1000).ok


def test_country_filter_applied():
    tpl = resolve_template("지난달 매출", "JP", TEST_TODAY)
    assert "p.country = 'JP'" in tpl.sql
    tpl = resolve_template("지난달 매출", "ALL", TEST_TODAY)
    assert "country =" not in tpl.sql


def test_date_filter_is_sargable():
    # 기간 조건은 컬럼을 함수로 감싸지 않는다 (인덱스 사용)
    tpl = resolve_template("지난달 매출", "ALL", TEST_TODAY)
    assert "p.paid_at >= '2026-09-01' AND p.paid_at < '2026-10-01'" in tpl.sql
    where_lines = [line for line in tpl.sql.splitlines() if line.strip().startswith(("WHERE", "AND"))]
    assert not any(re.search(r"(date|strftime)\(", line) for line in where_lines)


def test_bottom_rank_uses_asc_and_limit():
    tpl = resolve_template("매출 하위 5개 파트너사", "ALL", TEST_TODAY)
    assert "ASC" in tpl.sql and tpl.sql.rstrip().endswith("LIMIT 5")


def test_months_not_parsed_as_limit():
    # '최근 3개월'의 3을 LIMIT 3 으로 오인하지 않는다
    tpl = resolve_template("최근 3개월 업체별 매출", "ALL", TEST_TODAY)
    assert "LIMIT" not in tpl.sql


def test_partner_revenue_keeps_zero_revenue_partners():
    # 기간 필터를 LEFT JOIN ON 절에 둬서 매출 0 업체도 결과에 남는다
    tpl = resolve_template("오늘 업체별 매출", "ALL", TEST_TODAY)
    assert "LEFT JOIN coin_usages u ON" in tpl.sql
    assert "WHERE" not in tpl.sql
