"""
SQL 검증기 — 실행 전에 SQL 이 안전한지 확인한다 (sqlglot 파싱 기반).

검사 항목
  1. 한 문장만 허용 (세미콜론으로 여러 문장 이어 붙이기 차단)
  2. SELECT(또는 WITH ... SELECT, UNION) 만 허용 — INSERT/UPDATE/DELETE/DROP/ATTACH/PRAGMA 등 차단
  3. 허용된 테이블만 조회 (schema_info.ALLOWED_TABLES, CTE 이름은 제외)
  4. 민감 컬럼(password_hash 등) 조회 차단 — COUNT 같은 집계 안에 있어도 차단
  5. 개인정보가 있는 members 테이블은 SELECT * 금지 (필요한 컬럼만 명시)
  6. 위험 함수(load_extension 등) 차단
  7. LIMIT 이 없으면 붙이고, 상한보다 크면 줄인다
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
import sqlglot.expressions as exp
from sqlglot.errors import ParseError

from app.config import settings
from app.database.schema_info import ALLOWED_TABLES

SENSITIVE_COLUMNS: frozenset[str] = frozenset({"password_hash"})
_SENSITIVE_COL_RE = re.compile(r"(password|passwd|pwd|secret|token|ssn|card_?no|card_?number)", re.I)
_PII_STAR_TABLES: frozenset[str] = frozenset({"members"})
_FORBIDDEN_FUNCS: frozenset[str] = frozenset({"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"})
_FORBIDDEN_NODES = tuple(
    getattr(exp, name)
    for name in ("Insert", "Update", "Delete", "Drop", "Create", "Alter", "Command", "Pragma",
                 "Attach", "Detach", "Merge", "Transaction", "Commit", "Rollback")
    if hasattr(exp, name)
)


@dataclass
class ValidationResult:
    ok: bool
    sql: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)


def _strip_trailing_semicolons(sql: str) -> str:
    return re.sub(r"[;\s]+$", "", sql.strip())


def validate_sql(sql: str, max_rows: int | None = None) -> ValidationResult:
    max_rows = max_rows or settings.max_result_rows
    original = _strip_trailing_semicolons(sql or "")
    if not original:
        return ValidationResult(False, original, ["SQL 이 비어 있음"])

    # 1) 한 문장만
    try:
        statements = [s for s in sqlglot.parse(original, read="sqlite") if s is not None]
    except ParseError as e:
        return ValidationResult(False, original, [f"SQL 문법 오류: {str(e).splitlines()[0]}"])
    if len(statements) != 1:
        return ValidationResult(False, original, ["여러 문장을 한 번에 실행할 수 없음 (SELECT 한 문장만 허용)"])
    tree = statements[0]

    errors: list[str] = []
    warnings: list[str] = []

    # 2) SELECT 계열만
    forbidden = tree.find(*_FORBIDDEN_NODES) if _FORBIDDEN_NODES else None
    if isinstance(tree, _FORBIDDEN_NODES):
        errors.append(f"조회(SELECT)만 허용됨: '{tree.key.upper()}' 구문 차단")
    elif not isinstance(tree, (exp.Select, exp.SetOperation)):
        errors.append("SELECT 문이 아니거나 문법이 올바르지 않음")
    elif forbidden is not None:
        errors.append(f"데이터 변경/관리 구문 포함: {forbidden.key.upper()}")

    # 3) 테이블 화이트리스트 (CTE 이름 제외) + 테이블 함수(pragma_table_info 등) 차단
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    table_nodes = list(tree.find_all(exp.Table))
    table_funcs = [t.this for t in table_nodes if isinstance(t.this, exp.Func)]
    if table_funcs:
        name = getattr(table_funcs[0], "this", None) or table_funcs[0].key
        errors.append(f"테이블 함수는 사용할 수 없음: {name}")
    tables = sorted({t.name.lower() for t in table_nodes if t.name} - cte_names)
    unknown = [t for t in tables if t not in ALLOWED_TABLES]
    if unknown:
        errors.append(f"허용되지 않은 테이블: {', '.join(unknown)}")

    # 4) 민감 컬럼
    for col in tree.find_all(exp.Column):
        name = (col.name or "").lower()
        if name and (name in SENSITIVE_COLUMNS or _SENSITIVE_COL_RE.search(name)):
            errors.append(f"민감 컬럼 조회 금지: {name}")
            break

    # 5) 개인정보 테이블 SELECT * 금지 (COUNT(*) 는 허용)
    if any(t in _PII_STAR_TABLES for t in tables):
        for star in tree.find_all(exp.Star):
            if isinstance(star.parent, exp.Count):
                continue
            errors.append("members 테이블은 SELECT * 로 조회할 수 없음 (필요한 컬럼만 지정)")
            break

    # 6) 위험 함수
    for func in tree.find_all(exp.Anonymous):
        fname = str(func.this).lower()
        if fname in _FORBIDDEN_FUNCS or fname.startswith("pragma_"):
            errors.append(f"사용할 수 없는 함수: {func.this}")
            break

    if errors:
        return ValidationResult(False, original, errors, warnings, tables)

    # 7) LIMIT 강제
    final_sql = original
    limit_node = tree.args.get("limit")
    if limit_node is None:
        final_sql = f"{original}\nLIMIT {max_rows}"
        warnings.append(f"LIMIT 이 없어 {max_rows:,}행 제한을 추가함")
    else:
        try:
            value = int(limit_node.expression.name)
        except (AttributeError, TypeError, ValueError):
            value = None
        if value is None or value > max_rows:
            final_sql = tree.limit(max_rows).sql(dialect="sqlite", pretty=True)
            warnings.append(f"LIMIT 을 상한 {max_rows:,}행으로 조정함")

    return ValidationResult(True, final_sql, [], warnings, tables)
