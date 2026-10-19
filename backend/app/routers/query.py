import logging

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.database import app_db
from app.database.schema_info import schema_for_client
from app.pipeline.runner import run_query
from app.schemas import QueryRequest

router = APIRouter(prefix="/api", tags=["query"])
logger = logging.getLogger(__name__)

EXAMPLE_QUESTIONS = [
    "지난달 국가별 매출 알려줘",
    "최근 6개월 월별 매출 추이",
    "매출 하위 5개 파트너사",
    "올해 인기 작품 TOP 5",
    "장르별 매출 비중",
    "이번달 일별 신규 가입자 수",
    "지난달 탈퇴 회원 수",
    "최근 30일 DAU 추이",
    "최근 가입한 회원 목록 5명",
]


# 동기 함수로 둬서 FastAPI 스레드풀에서 실행 (SQLite·LLM 호출이 이벤트 루프를 막지 않게)
@router.post("/query")
def query(req: QueryRequest, user: dict = Depends(get_current_user)):
    result = run_query(req.question.strip(), req.country)
    blocked_step = next((s for s in result["steps"] if s["status"] in ("blocked", "error")), None)
    try:
        app_db.add_query_log({
            "login_id": user["login_id"],
            "country": result["country"],
            "question": req.question.strip(),
            "intent": result["intent"],
            "sql_source": result["sql_source"] or "none",
            "status": result["status"],
            "block_reason": blocked_step["detail"] if blocked_step else None,
            "sql": result["sql"],
            "row_count": result["row_count"],
            "elapsed_ms": result["elapsed_ms"],
        })
    except Exception:
        # 로그 저장 실패가 조회 응답을 막지는 않는다
        logger.exception("조회 로그 저장 실패")
    return result


@router.get("/schema")
def schema(user: dict = Depends(get_current_user)):
    return {"tables": schema_for_client()}


@router.get("/examples")
def examples():
    return {"items": EXAMPLE_QUESTIONS}
