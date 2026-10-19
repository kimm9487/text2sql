import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.database import sample_db  # noqa: E402

# 테스트는 날짜를 고정한 별도 DB 를 쓴다 (시연용 DB 를 건드리지 않고, 결과가 날짜에 따라 바뀌지 않게)
TEST_TODAY = date(2026, 10, 19)


@pytest.fixture(scope="session", autouse=True)
def test_databases(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    db_file = tmp / "content_platform_test.db"
    sample_db.build(db_file, TEST_TODAY)
    original = (settings.db_path, settings.app_db_path)
    settings.db_path = str(db_file)
    settings.app_db_path = str(tmp / "app_test.db")
    yield
    settings.db_path, settings.app_db_path = original
