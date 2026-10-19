"""
과제용 샘플 DB 생성 CLI (backend/ 에서 실행).

    python scripts/seed_db.py            # data/content_platform.db 가 없을 때만 생성
    python scripts/seed_db.py --reset    # 기존 파일 지우고 다시 생성
    python scripts/seed_db.py --end-date 2026-10-31

생성 로직은 app/database/sample_db.py 에 있다 (서버 첫 실행 시 자동 생성에도 같은 코드를 씀).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.sample_db import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
