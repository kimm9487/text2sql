"""
기간 해석 — 질문 속 날짜 표현을 실제 날짜 범위로 바꾼다.

비개발 직원은 "지난달", "요즘", "최근 3개월"처럼 묻기 때문에, SQL 을 만들기 전에
코드가 먼저 날짜를 확정해야 LLM 이 기간을 잘못 해석하는 일을 줄일 수 있다.

지원 표현
  - 오늘 / 어제 / 이번주 / 지난주 / 이번달 / 지난달 / 올해 / 작년
  - 최근 N일 / N주 / N개월 (N개월은 이번달 포함, 월초 기준)
  - 2026년 9월, 26년 9월, 2026-09, 작년 3월, 9월(올해)
  - 7월~9월, 2025년 11월부터 2026년 2월까지
  - 2026-09-01 ~ 2026-09-15, 2026년 9월 3일
  - 2025년
반환하는 end 는 '포함' 날짜. DATETIME 컬럼 필터는 sql_bounds() 의 반열림 구간을 쓴다.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date  # 포함
    label: str

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def sql_bounds(self) -> tuple[str, str]:
        """`col >= start AND col < end_exclusive` 용 문자열 두 개."""
        return self.start.isoformat(), (self.end + timedelta(days=1)).isoformat()

    def to_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "label": self.label}


def _month_range(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _year(token: str | None, today: date) -> int | None:
    if not token:
        return None
    if token in ("올해", "금년"):
        return today.year
    if token in ("작년", "지난해", "전년"):
        return today.year - 1
    y = int(token)
    return y + 2000 if y < 100 else y


def _valid_month(m: int) -> bool:
    return 1 <= m <= 12


# 숫자 연도는 뒤에 '년'이 붙을 때만 연도로 본다 ("TOP 10 9월"의 10을 2010년으로 오인 방지)
_YEAR_TOKEN = r"((?:\d{4}|\d{2})(?=\s*년)|올해|금년|작년|지난해|전년)\s*년?"

_PATTERNS_DATE_RANGE = re.compile(
    r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})\s*(?:~|부터|에서|-)\s*(\d{4})[-./](\d{1,2})[-./](\d{1,2})"
)
# 한글 표기는 '일'까지 있어야 특정 날짜로 본다 ("2026년 9월 10위"를 9월 10일로 오인 방지)
_PATTERN_SINGLE_DATE = re.compile(
    r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})|(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"
)
_PATTERN_MONTH_RANGE = re.compile(
    rf"(?:{_YEAR_TOKEN}\s*)?(\d{{1,2}})\s*월?\s*(?:~|부터|에서|-)\s*(?:{_YEAR_TOKEN}\s*)?(\d{{1,2}})\s*월"
)
_PATTERN_YEAR_MONTH = re.compile(rf"{_YEAR_TOKEN}\s*(\d{{1,2}})\s*월|(\d{{4}})-(\d{{1,2}})(?![\d-])")
_PATTERN_MONTH_ONLY = re.compile(r"(?<!\d)(\d{1,2})\s*월(?!별)")
_PATTERN_YEAR_ONLY = re.compile(r"(\d{4})\s*년")
_PATTERN_RECENT = re.compile(r"(?:최근|지난)\s*(\d+)\s*(일|주|개월|달)")


def parse_date_range(question: str, today: date | None = None) -> DateRange | None:
    today = today or date.today()
    q = question or ""

    # 1) 명시적 날짜 범위
    m = _PATTERNS_DATE_RANGE.search(q)
    if m:
        try:
            s = date(int(m[1]), int(m[2]), int(m[3]))
            e = date(int(m[4]), int(m[5]), int(m[6]))
            if s <= e:
                return DateRange(s, e, f"{s} ~ {e}")
        except ValueError:
            pass

    # 2) 최근 N일/주/개월 (오늘 포함)
    m = _PATTERN_RECENT.search(q)
    if m:
        n, unit = int(m[1]), m[2]
        if n > 0:
            if unit == "일":
                start = today - timedelta(days=n - 1)
                label = f"최근 {n}일"
            elif unit == "주":
                start = today - timedelta(days=7 * n - 1)
                label = f"최근 {n}주"
            else:
                # 'N개월'은 이번달 포함 N개월, 월초부터 (월별 추이에서 첫 달이 잘리지 않게)
                y, mo = divmod(today.year * 12 + today.month - 1 - (n - 1), 12)
                start = date(y, mo + 1, 1)
                label = f"최근 {n}개월"
            return DateRange(start, today, label)

    # 3) 상대 표현
    compact = re.sub(r"\s+", "", q)
    if "오늘" in compact or "금일" in compact:
        return DateRange(today, today, "오늘")
    if "어제" in compact or "전일" in compact:
        y = today - timedelta(days=1)
        return DateRange(y, y, "어제")
    if any(k in compact for k in ("이번주", "금주")):
        start = today - timedelta(days=today.weekday())
        return DateRange(start, today, "이번주")
    if any(k in compact for k in ("지난주", "저번주", "전주")):
        start = today - timedelta(days=today.weekday() + 7)
        return DateRange(start, start + timedelta(days=6), "지난주")
    if any(k in compact for k in ("이번달", "이달", "당월", "금월")):
        return DateRange(today.replace(day=1), today, "이번달")
    if any(k in compact for k in ("지난달", "저번달", "전월")):
        last_prev = today.replace(day=1) - timedelta(days=1)
        return DateRange(last_prev.replace(day=1), last_prev, "지난달")

    # 4) 월 범위 (7월~9월, 2025년 11월부터 2026년 2월까지)
    m = _PATTERN_MONTH_RANGE.search(q)
    if m:
        y1, m1, y2, m2 = _year(m[1], today), int(m[2]), _year(m[3], today), int(m[4])
        if _valid_month(m1) and _valid_month(m2):
            y2 = y2 or y1 or today.year
            y1 = y1 or (y2 if m1 <= m2 else y2 - 1)
            s, _ = _month_range(y1, m1)
            _, e = _month_range(y2, m2)
            if s <= e:
                return DateRange(s, e, f"{y1}년 {m1}월 ~ {y2}년 {m2}월")

    # 5) 특정 날짜 (2026년 9월 3일, 2026-09-03)
    m = _PATTERN_SINGLE_DATE.search(q)
    if m:
        y, mo, d = (m[1], m[2], m[3]) if m[1] else (m[4], m[5], m[6])
        try:
            day = date(int(y), int(mo), int(d))
            return DateRange(day, day, day.isoformat())
        except ValueError:
            pass

    # 6) 연-월 (2026년 9월, 작년 3월, 2026-09)
    m = _PATTERN_YEAR_MONTH.search(q)
    if m:
        if m[1]:
            y, mo = _year(m[1], today), int(m[2])
        else:
            y, mo = int(m[3]), int(m[4])
        if y and _valid_month(mo):
            s, e = _month_range(y, mo)
            return DateRange(s, e, f"{y}년 {mo}월")

    # 7) 올해 / 작년
    if "올해" in compact or "금년" in compact:
        return DateRange(date(today.year, 1, 1), today, "올해")
    if any(k in compact for k in ("작년", "지난해", "전년")):
        return DateRange(date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), "작년")

    # 8) 월만 (연도 없으면 올해)
    m = _PATTERN_MONTH_ONLY.search(q)
    if m and _valid_month(int(m[1])):
        mo = int(m[1])
        s, e = _month_range(today.year, mo)
        return DateRange(s, e, f"{today.year}년 {mo}월")

    # 9) 연도만
    m = _PATTERN_YEAR_ONLY.search(q)
    if m:
        y = int(m[1])
        return DateRange(date(y, 1, 1), date(y, 12, 31), f"{y}년")

    return None
