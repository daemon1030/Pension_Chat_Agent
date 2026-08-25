"""이미 실행 중인 PostgreSQL에 초기 Schema를 적용한다."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import connect_from_env


def main() -> None:
    schema = (PROJECT_ROOT / "database" / "init.sql").read_text(encoding="utf-8")
    with connect_from_env() as connection:
        connection.execute(schema)
    print("PostgreSQL + pgvector Schema 적용 완료")


if __name__ == "__main__":
    main()
