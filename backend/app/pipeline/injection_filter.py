"""
입력 필터 — LLM/DB 호출 전에 위험한 질문을 먼저 걸러낸다.

1) 프롬프트 인젝션: "이전 지시 무시해", "DROP TABLE" 같은 패턴
2) 민감 개인정보 직접 조회 요청: 비밀번호·주민번호·카드번호 등은 분석 대상이 아니므로
   SQL 을 만들기 전에 차단하고 이유를 알려준다.

띄어쓰기/구두점 우회("비 밀 번 호", "주.민.번.호")를 막기 위해 NFKC 정규화 후
한글·영숫자 외 문자를 전부 지운 문자열에서 검사한다.

TODO(기말): '토큰', 'ip' 처럼 짧고 일반 질문에도 자주 나오는 단어는 지금 목록에서 뺐음.
            앞뒤 문맥(조회 의도인지)을 보고 판단하는 방식으로 보강 예정.
"""
from __future__ import annotations

import re
import unicodedata

INJECTION_PATTERNS: list[str] = [
    r"ignore (previous|above|all) (instructions|prompts)",
    r"이전\s*(지시|명령|프롬프트)\s*(를|을)?\s*무시",
    r"시스템\s*프롬프트",
    r"\bsystem\s*:\s*",
    r"<\s*system\s*>",
    r"act as (admin|root|developer)",
    r"관리자(로|처럼)\s*행동",
    r"\bDROP\s+TABLE\b",
    r"\bDELETE\s+FROM\b",
    r"\bUPDATE\s+\w+\s+SET\b",
    r"\bINSERT\s+INTO\b",
    r"\bALTER\s+TABLE\b",
]
_INJECTION_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# (사유 카테고리, 용어) — 정규화 문자열에 포함되면 차단
_SENSITIVE_TERMS: list[tuple[str, str]] = [
    ("비밀번호", "비밀번호"), ("비밀번호", "패스워드"), ("비밀번호", "password"),
    ("비밀번호", "passwd"), ("비밀번호", "passwordhash"),
    ("주민등록번호", "주민등록번호"), ("주민등록번호", "주민번호"), ("주민등록번호", "외국인등록번호"),
    ("카드정보", "카드번호"), ("카드정보", "카드비밀번호"), ("카드정보", "cardnumber"),
    ("카드정보", "cvc번호"),
    ("인증정보", "인증토큰"), ("인증정보", "accesstoken"), ("인증정보", "apikey"),
    ("인증정보", "secretkey"),
    ("접속IP", "접속ip"), ("접속IP", "로그인ip"), ("접속IP", "ipaddress"),
]

# 짧은 영문 약어는 단어 경계로만 매칭 ("businessnews" 의 ssn 오탐 방지)
_ACRONYMS: list[tuple[str, re.Pattern]] = [
    ("주민등록번호", re.compile(r"(?<![a-z0-9])ssn(?![a-z0-9])")),
    ("카드정보", re.compile(r"(?<![a-z0-9])cvv(?![a-z0-9])")),
]


def _normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"[^0-9a-z가-힣]+", "", t)


def detect_injection(text: str) -> str | None:
    """인젝션 패턴이 있으면 매칭된 패턴, 없으면 None."""
    for pattern in _INJECTION_COMPILED:
        if pattern.search(text or ""):
            return pattern.pattern
    return None


def detect_sensitive_request(text: str) -> str | None:
    """민감 개인정보 직접 조회 요청이면 카테고리 이름, 아니면 None."""
    norm = _normalize(text)
    for category, term in _SENSITIVE_TERMS:
        if term in norm:
            return category
    lowered = unicodedata.normalize("NFKC", text or "").lower()
    for category, pattern in _ACRONYMS:
        if pattern.search(lowered):
            return category
    return None
