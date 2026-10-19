"""
의도 분류 — 키워드 기반 (LLM 호출 없음).

  sql     : 데이터 질문 → SQL 생성 단계로
  weather : 날씨 질문 → 중간 단계에서는 안내 문구만 (외부 날씨 API 연동은 기말 예정)
  chat    : 인사·잡담 → 고정 응답
"""
from __future__ import annotations

import re

_DATA_KEYWORDS = [
    "매출", "결제", "환불", "회원", "가입", "탈퇴", "이탈", "휴면", "작품", "작가", "파트너", "업체", "cp",
    "장르", "코인", "로그인", "접속", "dau", "mau", "활성", "사용자", "유저", "건수", "몇 명", "몇명",
    "합계", "평균", "추이", "순위", "top", "상위", "하위", "비중", "비율", "국가별", "일별", "월별",
    "통계", "수익", "구매", "회차", "연재", "완결", "조회", "보여줘", "알려줘", "얼마",
]
_WEATHER_KEYWORDS = ["날씨", "기온", "미세먼지", "비 와", "비와", "눈 와", "우산"]
_CHAT_PATTERNS = [
    r"^(안녕|하이|hello|hi)\b", r"고마워|감사합니다|땡큐", r"너는?\s*누구", r"뭐\s*해", r"심심",
]

CHAT_REPLIES = {
    "greeting": "안녕하세요. 매출·회원·작품 데이터에 대해 질문하면 SQL로 조회해서 표와 차트로 보여드립니다.",
    "thanks": "도움이 됐다니 다행입니다. 다른 데이터도 궁금하면 질문해 주세요.",
    "default": "데이터 조회 서비스라 일상 대화는 간단한 답만 가능합니다. 예: \"지난달 국가별 매출 알려줘\"",
    "weather": "날씨 조회 기능은 아직 연결 전입니다 (기말까지 외부 날씨 API 연동 예정). 지금은 데이터 질문만 처리할 수 있습니다.",
}


def classify_intent(question: str) -> str:
    q = (question or "").strip().lower()
    if any(k in q for k in _WEATHER_KEYWORDS):
        return "weather"
    if any(k in q for k in _DATA_KEYWORDS):
        return "sql"
    if any(re.search(p, q) for p in _CHAT_PATTERNS):
        return "chat"
    # 분류가 애매하면 데이터 질문으로 본다 (조회 서비스가 본 목적이므로)
    return "sql" if len(q) >= 8 else "chat"


def chat_reply(question: str, intent: str) -> str:
    if intent == "weather":
        return CHAT_REPLIES["weather"]
    q = (question or "").lower()
    if re.search(r"고마워|감사|땡큐", q):
        return CHAT_REPLIES["thanks"]
    if re.search(r"^(안녕|하이|hello|hi)\b", q):
        return CHAT_REPLIES["greeting"]
    return CHAT_REPLIES["default"]
