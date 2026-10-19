"""
환경설정 — backend/.env 를 읽는다 (.env.example 참고).

경로 값은 backend 디렉터리 기준 상대경로로 받고, 실제 사용 시 절대경로로 바꾼다
(uvicorn 을 어느 위치에서 실행해도 같은 DB 파일을 보도록).
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # 조회 대상 DB (과제용 샘플 DB) / 앱 DB (계정·조회 로그)
    db_path: str = "data/content_platform.db"
    app_db_path: str = "data/app.db"

    # JWT
    jwt_secret_key: str = "local-dev-secret-key-change-me-in-dotenv"  # 시연용 기본값, .env 에서 교체
    jwt_expire_minutes: int = 120

    # LLM — none 이면 템플릿 질문만 처리 (중간 단계 기본값)
    llm_provider: str = "none"          # none | claude
    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "medium"
    anthropic_api_key: str | None = None

    # 실행 제한
    query_timeout_sec: float = 5.0
    max_result_rows: int = 1000

    @property
    def db_file(self) -> Path:
        return (BASE_DIR / self.db_path).resolve()

    @property
    def app_db_file(self) -> Path:
        return (BASE_DIR / self.app_db_path).resolve()

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider == "claude" and bool(self.anthropic_api_key)


settings = Settings()
