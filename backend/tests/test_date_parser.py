from datetime import date

import pytest

from app.pipeline.date_parser import parse_date_range

TODAY = date(2026, 10, 19)  # 월요일


@pytest.mark.parametrize("q, start, end", [
    ("오늘 매출", "2026-10-19", "2026-10-19"),
    ("어제 매출", "2026-10-18", "2026-10-18"),
    ("이번주 매출", "2026-10-19", "2026-10-19"),
    ("지난주 매출", "2026-10-12", "2026-10-18"),
    ("이번달 매출", "2026-10-01", "2026-10-19"),
    ("이번 달 매출", "2026-10-01", "2026-10-19"),
    ("지난달 매출", "2026-09-01", "2026-09-30"),
    ("최근 7일 매출", "2026-10-13", "2026-10-19"),
    ("최근 3개월 매출", "2026-08-01", "2026-10-19"),
    ("최근 12개월 매출", "2025-11-01", "2026-10-19"),
    ("2026년 9월 매출", "2026-09-01", "2026-09-30"),
    ("26년 2월 매출", "2026-02-01", "2026-02-28"),
    ("2026-08 매출", "2026-08-01", "2026-08-31"),
    ("작년 3월 매출", "2025-03-01", "2025-03-31"),
    ("9월 매출", "2026-09-01", "2026-09-30"),
    ("7월~9월 매출", "2026-07-01", "2026-09-30"),
    ("2025년 11월부터 2026년 2월까지 매출", "2025-11-01", "2026-02-28"),
    ("2026-09-01 ~ 2026-09-15 매출", "2026-09-01", "2026-09-15"),
    ("2026년 9월 3일 매출", "2026-09-03", "2026-09-03"),
    ("올해 매출", "2026-01-01", "2026-10-19"),
    ("작년 매출", "2025-01-01", "2025-12-31"),
    ("2025년 매출", "2025-01-01", "2025-12-31"),
])
def test_parses_period(q, start, end):
    dr = parse_date_range(q, TODAY)
    assert dr is not None, q
    assert (dr.start.isoformat(), dr.end.isoformat()) == (start, end)


def test_no_period():
    assert parse_date_range("국가별 매출", TODAY) is None


def test_monthly_keyword_is_not_month():
    # '월별'의 '월'을 특정 월로 보지 않는다
    assert parse_date_range("월별 매출 추이", TODAY) is None


def test_rank_number_not_parsed_as_year_or_day():
    dr = parse_date_range("2026년 9월 매출 10위까지", TODAY)
    assert (dr.start.isoformat(), dr.end.isoformat()) == ("2026-09-01", "2026-09-30")
    dr = parse_date_range("TOP 10 9월 매출", TODAY)
    assert dr.start.year == 2026


def test_sql_bounds_half_open():
    dr = parse_date_range("지난달 매출", TODAY)
    assert dr.sql_bounds() == ("2026-09-01", "2026-10-01")
