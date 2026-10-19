"""
앱 DB (SQLite) — 로그인 계정 + 조회 로그.

조회 대상 DB(content_platform.db)와 파일을 분리해서, 조회 대상 DB 는 항상 읽기전용으로만 연다.

중간 단계 범위:
  - 계정: 데모 계정 2개(직원/관리자)를 자동 생성. 가입 신청 → 관리자 승인, 10회 실패 잠금은 기말 예정.
  - 조회 로그: 질문·SQL·결과 상태를 기록하고 관리자 화면에서 조회. 해시 체인(위변조 방지)은 기말 예정.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY,
    login_id       TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    department     TEXT NOT NULL,
    role           TEXT NOT NULL,          -- employee / admin
    password_salt  TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS query_logs (
    id            INTEGER PRIMARY KEY,
    created_at    TEXT NOT NULL,
    login_id      TEXT,
    country       TEXT NOT NULL,
    question      TEXT NOT NULL,
    intent        TEXT,
    sql_source    TEXT,                    -- template / llm / none
    status        TEXT NOT NULL,           -- success / blocked / error / chat
    block_reason  TEXT,
    sql           TEXT,
    row_count     INTEGER,
    elapsed_ms    INTEGER
);
"""

# 시연용 데모 계정 (README 에 안내)
DEMO_USERS = [
    ("demo", "demo1234", "김직원", "마케팅팀", "employee"),
    ("admin", "admin1234", "박관리", "데이터팀", "admin"),
]


def _connect() -> sqlite3.Connection:
    settings.app_db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.app_db_file)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000).hex()


def init_app_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        for login_id, password, name, dept, role in DEMO_USERS:
            exists = conn.execute("SELECT 1 FROM users WHERE login_id = ?", (login_id,)).fetchone()
            if exists:
                continue
            salt = os.urandom(16).hex()
            conn.execute(
                "INSERT INTO users (login_id, name, department, role, password_salt, password_hash, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (login_id, name, dept, role, salt, hash_password(password, salt), _now()),
            )


def verify_user(login_id: str, password: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE login_id = ?", (login_id,)).fetchone()
    if not row:
        return None
    if not hmac.compare_digest(row["password_hash"], hash_password(password, row["password_salt"])):
        return None
    return {k: row[k] for k in ("id", "login_id", "name", "department", "role")}


def get_user(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, login_id, name, department, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def add_query_log(entry: dict) -> None:
    cols = ["login_id", "country", "question", "intent", "sql_source", "status",
            "block_reason", "sql", "row_count", "elapsed_ms"]
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO query_logs (created_at, {', '.join(cols)}) VALUES (?, {', '.join('?' * len(cols))})",
            (_now(), *[entry.get(c) for c in cols]),
        )


def list_query_logs(limit: int = 100, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM query_logs"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_log_stats() -> dict:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(status = 'success') AS success,
                   SUM(status = 'blocked') AS blocked,
                   SUM(status = 'error') AS error,
                   SUM(sql_source = 'template') AS template,
                   SUM(sql_source = 'llm') AS llm,
                   SUM(date(created_at) = date('now', 'localtime')) AS today
            FROM query_logs
            """
        ).fetchone()
    return {k: (row[k] or 0) for k in row.keys()}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
