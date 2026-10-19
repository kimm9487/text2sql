from fastapi import APIRouter

from app.config import settings
from app.database.sqlite_client import check_connection

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    db_ok = check_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "llm": {"provider": settings.llm_provider, "enabled": settings.llm_enabled, "model": settings.llm_model},
    }
