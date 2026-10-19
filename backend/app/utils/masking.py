"""
결과 마스킹 — 쿼리 결과의 이메일·전화번호·주민등록번호를 가린다.

SQL 검증을 통과한 정상 조회라도 결과에 개인정보가 섞일 수 있으므로
화면으로 보내기 직전에 모든 문자열 값에 적용한다 (원본 rows 는 바꾸지 않음).
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_PHONE_RE = re.compile(
    r"(?<!\d)(?:"
    r"\+(?:886|82|81)[-\s]\d{1,4}[-\s]\d{3,4}[-\s]\d{3,4}"   # 국제번호
    r"|01[0-9][-\s]?\d{3,4}[-\s]?\d{4}"                       # KR 휴대폰
    r"|09\d{2}[-\s]?\d{3}[-\s]?\d{3}"                         # TW 휴대폰
    r"|0[789]0[-\s]?\d{4}[-\s]?\d{4}"                         # JP 휴대폰
    r"|0\d{1,3}[-\s]\d{3,4}[-\s]\d{4}"                        # 유선
    r")(?!\d)"
)

_RRN_RE = re.compile(r"(?<!\d)\d{6}[-\s]?[1-8]\d{6}(?!\d)")


def _mask_email(email: str) -> str:
    """user@example.com → u***@example.com"""
    at = email.find("@")
    if at <= 1:
        return "***@" + email[at + 1:]
    return email[0] + "***" + email[at:]


def _mask_phone(phone: str) -> str:
    """010-1234-5678 → 010-****-5678, 0912-345-678 → 0912-***-678"""
    if phone.startswith("+"):
        parts = re.split(r"[-\s]", phone)
        if len(parts) >= 3:
            return "-".join(parts[:-2] + ["****", parts[-1]])
        return phone[:4] + "-****-" + phone[-4:]
    digits = re.sub(r"\D", "", phone)
    n = len(digits)
    if n >= 11:
        return f"{digits[:3]}-****-{digits[7:]}"
    if n == 10:
        return f"{digits[:4]}-***-{digits[7:]}"
    return "***-****-****"


def mask_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = _EMAIL_RE.sub(lambda m: _mask_email(m.group()), value)
    value = _PHONE_RE.sub(lambda m: _mask_phone(m.group()), value)
    value = _RRN_RE.sub("******-*******", value)
    return value


# 사람 이름 컬럼 (값 패턴으로는 알 수 없어서 컬럼명으로 판단) — '업체명'·'작품명'·'필명'은 제외
NAME_COLUMNS = frozenset({"name", "이름", "회원명", "회원이름", "성명", "고객명"})


def mask_name(name: str) -> str:
    """강민준 → 강*준, 김수 → 김*, Lee Yu → L****u"""
    n = len(name)
    if n <= 1:
        return "*"
    if n == 2:
        return name[0] + "*"
    return name[0] + "*" * (n - 2) + name[-1]


def mask_rows(rows: list[dict]) -> tuple[list[dict], int]:
    """마스킹한 새 rows 와 마스킹된 값 개수를 반환."""
    masked_count = 0
    out: list[dict] = []
    for row in rows:
        new_row = {}
        for k, v in row.items():
            if isinstance(v, str) and k.lower() in NAME_COLUMNS:
                mv = mask_name(v)
            else:
                mv = mask_value(v)
            if mv != v:
                masked_count += 1
            new_row[k] = mv
        out.append(new_row)
    return out, masked_count
