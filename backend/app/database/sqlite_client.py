"""
조회 대상 DB 실행기 — 읽기전용 강제 + 시간/행 수 제한.

읽기전용은 3단계로 막는다 (워크시트 4번 '3중 차단'):
  1) 입력 필터 (pipeline/injection_filter.py)
  2) SQL 검증기 — SELECT 단일문만 통과 (pipeline/sql_validator.py)
  3) 여기 — DB 커넥션 자체를 읽기전용(mode=ro + query_only)으로 열어서
     앞 단계가 뚫려도 DB 가 직접 쓰기를 거부하게 한다.
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field

from app.config import settings


class ReadOnlyViolation(Exception):
    """SELECT 가 아닌 구문이 실행 단계까지 넘어온 경우."""


class QueryTimeout(Exception):
    """실행 시간 제한 초과."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict]
    elapsed_ms: int
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)


_COMMENT_RE = re.compile(r"/\*.*?\*/|--[^\n]*", re.S)


def _assert_readonly(sql: str) -> None:
    """앱 계층 관문 — 주석을 걷어낸 뒤 첫 키워드가 SELECT/WITH 인지 확인."""
    stripped = _COMMENT_RE.sub(" ", sql).strip().lstrip("(").strip()
    first = stripped.split(None, 1)[0].upper() if stripped else ""
    if first not in ("SELECT", "WITH"):
        raise ReadOnlyViolation(f"읽기전용 위반: '{first or '(빈 문장)'}' 구문은 실행할 수 없음")


def get_readonly_connection() -> sqlite3.Connection:
    uri = f"file:{settings.db_file.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def execute_select(sql: str, max_rows: int | None = None, timeout_sec: float | None = None) -> QueryResult:
    _assert_readonly(sql)
    max_rows = max_rows or settings.max_result_rows
    timeout_sec = timeout_sec or settings.query_timeout_sec

    conn = get_readonly_connection()
    started = time.perf_counter()
    deadline = started + timeout_sec

    # SQLite 는 쿼리 타임아웃 옵션이 없어서 progress handler 로 시간 초과 시 중단시킨다
    def _check_deadline() -> int:
        return 1 if time.perf_counter() > deadline else 0

    conn.set_progress_handler(_check_deadline, 10_000)
    try:
        cur = conn.execute(sql)
        fetched = cur.fetchmany(max_rows + 1)
        columns = [d[0] for d in cur.description] if cur.description else []
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e):
            raise QueryTimeout(f"실행 시간 {timeout_sec:.0f}초 초과로 중단함") from e
        raise
    finally:
        conn.close()

    truncated = len(fetched) > max_rows
    rows = [dict(r) for r in fetched[:max_rows]]
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    warnings = [f"결과가 많아 앞 {max_rows:,}행만 표시함"] if truncated else []
    return QueryResult(columns=columns, rows=rows, elapsed_ms=elapsed_ms, truncated=truncated, warnings=warnings)


def check_connection() -> bool:
    try:
        conn = get_readonly_connection()
        conn.execute("SELECT 1 FROM members LIMIT 1")
        conn.close()
        return True
    except Exception:
        return False
