from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.auth import require_admin
from app.database import app_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/logs")
def logs(
    status: Literal["success", "blocked", "error", "chat"] | None = None,
    limit: int = Query(100, ge=1, le=500),
    admin: dict = Depends(require_admin),
):
    return {"stats": app_db.query_log_stats(), "items": app_db.list_query_logs(limit, status)}
