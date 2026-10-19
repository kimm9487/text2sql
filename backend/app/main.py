"""
FastAPI 앱 진입점 — uvicorn app.main:app

- 첫 실행 시 과제용 샘플 DB 와 앱 DB(데모 계정)를 자동 생성
- /api/* : 백엔드 API
- 그 외 경로 : frontend 빌드 결과(backend/static)를 서빙 (npm run build 후)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, settings
from app.database import app_db, sample_db
from app.routers import admin, auth, health, query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("text2sql")

STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if sample_db.ensure_db(settings.db_file):
        logger.info("샘플 DB 생성: %s", settings.db_file)
    app_db.init_app_db()
    logger.info("LLM: provider=%s enabled=%s model=%s", settings.llm_provider, settings.llm_enabled, settings.llm_model)
    yield


app = FastAPI(title="Text2SQL (캡스톤디자인 중간 시연)", version="0.5.0", lifespan=lifespan)

# 개발 중 Vite dev server(5173)에서 호출할 수 있게
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(query.router)
app.include_router(admin.router)
app.include_router(health.router)

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return JSONResponse(
            {"detail": "프론트엔드 빌드가 없습니다. frontend 에서 npm run build 를 실행하거나 npm run dev 로 접속하세요."},
            status_code=404,
        )
    return FileResponse(index)
