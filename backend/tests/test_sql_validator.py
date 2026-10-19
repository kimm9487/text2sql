import pytest

from app.pipeline.sql_validator import validate_sql


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM members",
    "SELECT country, SUM(amount) AS 매출 FROM payments WHERE status = 'paid' GROUP BY country",
    "WITH t AS (SELECT member_id FROM payments) SELECT COUNT(*) FROM t",
    "SELECT name, email FROM members LIMIT 10",
    "SELECT country FROM payments UNION SELECT country FROM members",
    "SELECT 1;",
])
def test_allows_safe_select(sql):
    assert validate_sql(sql, 1000).ok


@pytest.mark.parametrize("sql, reason", [
    ("DELETE FROM members", "조회(SELECT)만"),
    ("UPDATE members SET name = 'x'", "조회(SELECT)만"),
    ("DROP TABLE members", "조회(SELECT)만"),
    ("INSERT INTO members (name) VALUES ('x')", "조회(SELECT)만"),
    ("PRAGMA table_info(members)", "조회(SELECT)만"),
    ("ATTACH DATABASE 'x.db' AS x", "조회(SELECT)만"),
    ("WITH x AS (SELECT 1) UPDATE members SET name = 1", "조회(SELECT)만"),
    ("SELECT 1; DROP TABLE members", "여러 문장"),
    ("SELECT name FROM sqlite_master", "허용되지 않은 테이블"),
    ("SELECT * FROM pragma_table_info('members')", "테이블 함수"),
    ("SELECT password_hash FROM members", "민감 컬럼"),
    ("SELECT COUNT(password_hash) FROM members", "민감 컬럼"),
    ("SELECT * FROM members", "SELECT *"),
    ("SELECT m.* FROM members m", "SELECT *"),
    ("SELECT load_extension('x')", "사용할 수 없는 함수"),
    ("SELEC broken", "SELECT 문이 아니"),
    ("", "비어"),
])
def test_blocks_unsafe_sql(sql, reason):
    r = validate_sql(sql, 1000)
    assert not r.ok
    assert any(reason in e for e in r.errors), r.errors


def test_count_star_on_members_is_allowed():
    assert validate_sql("SELECT COUNT(*) FROM members WHERE status = 'active'", 1000).ok


def test_adds_limit_when_missing():
    r = validate_sql("SELECT country FROM payments", 500)
    assert r.ok and r.sql.rstrip().endswith("LIMIT 500")


def test_clamps_large_limit():
    r = validate_sql("SELECT country FROM payments LIMIT 99999", 500)
    assert r.ok and "LIMIT 500" in r.sql and "99999" not in r.sql


def test_keeps_small_limit():
    r = validate_sql("SELECT country FROM payments LIMIT 5", 500)
    assert r.ok and r.sql.endswith("LIMIT 5")


def test_cte_name_not_treated_as_unknown_table():
    r = validate_sql("WITH monthly AS (SELECT * FROM payments) SELECT COUNT(*) FROM monthly", 100)
    assert r.ok
    assert r.tables == ["payments"]
