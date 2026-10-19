"""
조회 대상 DB 스키마 설명.

- LLM 프롬프트에 넣는 스키마 문서
- 화면의 '조회 가능한 데이터' 안내
- SQL 검증기의 테이블 화이트리스트
세 곳이 이 파일 하나를 기준으로 쓴다.

※ 지금은 테이블이 7개라 프롬프트에 전부 넣지만, 기말에는 스키마 설명·정답 쿼리를
  벡터DB 에 넣고 질문과 관련된 것만 검색(RAG)해서 넣는 방식으로 바꿀 예정.
"""
from __future__ import annotations

TABLES: dict[str, dict] = {
    "partners": {
        "label": "파트너사(CP)",
        "description": "작품을 공급하는 콘텐츠 제공 업체",
        "columns": {
            "partner_id": "업체 ID (PK)",
            "partner_name": "업체명",
            "country": "업체 소속 국가 (KR/JP/TW)",
            "contract_type": "계약 형태 exclusive=독점, non_exclusive=비독점",
            "revenue_share": "정산 비율 (0.6 = 60%)",
            "contact_email": "담당자 이메일 (개인정보 — 조회 지양)",
            "joined_at": "계약 시작일 (DATE)",
        },
    },
    "authors": {
        "label": "작가",
        "description": "작품을 쓴 작가. 하나의 파트너사에 소속",
        "columns": {
            "author_id": "작가 ID (PK)",
            "pen_name": "필명",
            "partner_id": "소속 업체 ID (partners.partner_id)",
        },
    },
    "contents": {
        "label": "작품",
        "description": "연재 중이거나 완결된 웹소설 작품",
        "columns": {
            "content_id": "작품 ID (PK)",
            "title": "작품명",
            "genre": "장르 (로맨스/판타지/로맨스판타지/무협/현대판타지/드라마/미스터리/코미디)",
            "author_id": "작가 ID (authors.author_id)",
            "partner_id": "공급 업체 ID (partners.partner_id)",
            "price_per_episode": "회차당 코인",
            "total_episodes": "총 회차 수",
            "is_completed": "완결 여부 (1=완결, 0=연재중)",
            "released_at": "연재 시작일 (DATE)",
        },
    },
    "members": {
        "label": "회원",
        "description": "서비스 회원. 이름·이메일·전화번호는 개인정보라 결과에서 마스킹됨",
        "columns": {
            "member_id": "회원 ID (PK)",
            "name": "이름 (개인정보)",
            "email": "이메일 (개인정보)",
            "phone": "전화번호 (개인정보)",
            "password_hash": "비밀번호 해시 (조회 금지 — 검증기가 차단)",
            "country": "국가 (KR/JP/TW)",
            "gender": "성별 (M/F)",
            "birth_year": "출생연도",
            "signup_channel": "가입 경로 (organic/google/kakao/line/apple/ad)",
            "status": "상태 (active=활성, dormant=휴면, withdrawn=탈퇴)",
            "joined_at": "가입일시 (DATETIME)",
            "last_login_at": "마지막 로그인 일시",
            "withdrawn_at": "탈퇴일시 (탈퇴 회원만 값 있음)",
        },
    },
    "payments": {
        "label": "결제(코인 충전)",
        "description": "코인 충전 결제 내역. 플랫폼 매출은 이 테이블 기준 (status='paid' 만 매출)",
        "columns": {
            "payment_id": "결제 ID (PK)",
            "member_id": "회원 ID (members.member_id)",
            "country": "결제 국가 (KR/JP/TW)",
            "amount": "결제 금액 (원 환산)",
            "coins": "지급 코인 수",
            "method": "결제수단 (card=카드, mobile=휴대폰, easy_pay=간편결제, in_app=인앱결제)",
            "status": "결제 상태 (paid=완료, refunded=환불)",
            "paid_at": "결제일시 (DATETIME)",
        },
    },
    "coin_usages": {
        "label": "코인 사용(회차 구매)",
        "description": "작품 회차 구매에 코인을 쓴 내역. 작품별·업체별 매출은 SUM(coins) * 100 (원)",
        "columns": {
            "usage_id": "사용 ID (PK)",
            "member_id": "회원 ID (members.member_id)",
            "content_id": "작품 ID (contents.content_id)",
            "country": "국가 (KR/JP/TW)",
            "episodes": "구매 회차 수",
            "coins": "사용 코인 (1코인 = 100원)",
            "used_at": "사용일시 (DATETIME)",
        },
    },
    "login_logs": {
        "label": "로그인 기록",
        "description": "회원 로그인 기록. DAU/MAU 는 COUNT(DISTINCT member_id)",
        "columns": {
            "log_id": "로그 ID (PK)",
            "member_id": "회원 ID (members.member_id)",
            "country": "국가 (KR/JP/TW)",
            "device": "기기 (android/ios/web)",
            "login_at": "로그인 일시 (DATETIME)",
        },
    },
}

ALLOWED_TABLES: frozenset[str] = frozenset(TABLES)

# 개인정보 컬럼 — 결과 마스킹 대상이고, LLM 에도 '집계 외 조회 금지'로 안내
PII_COLUMNS: frozenset[str] = frozenset({"name", "email", "phone", "contact_email"})


def schema_prompt_text() -> str:
    """LLM 프롬프트용 스키마 문서."""
    lines: list[str] = []
    for table, info in TABLES.items():
        lines.append(f"### {table} — {info['label']}: {info['description']}")
        for col, desc in info["columns"].items():
            lines.append(f"- {col}: {desc}")
        lines.append("")
    return "\n".join(lines).strip()


def schema_for_client() -> list[dict]:
    """화면 안내용 (비밀번호 해시 같은 민감 컬럼 설명은 그대로 노출해도 값은 못 봄)."""
    return [
        {
            "table": table,
            "label": info["label"],
            "description": info["description"],
            "columns": [{"name": c, "description": d} for c, d in info["columns"].items()],
        }
        for table, info in TABLES.items()
    ]
