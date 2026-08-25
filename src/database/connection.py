"""환경변수 기반 PostgreSQL 연결 생성."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from src.rag.naver_embedding import load_local_env


class DatabaseConnectionError(RuntimeError):
    """DB 연결 설정 또는 psycopg 설치 문제를 사용자에게 설명한다."""


@dataclass(frozen=True)
class DatabaseSettings:
    dsn: str

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        load_local_env()
        dsn = os.getenv("PENSION_DATABASE_DSN")
        if not dsn:
            raise DatabaseConnectionError(
                "PENSION_DATABASE_DSN이 설정되지 않았습니다. .env.example을 참고하세요."
            )
        return cls(dsn=dsn)


def connect_from_env() -> Any:
    """psycopg를 지연 import하여 DB 기능을 쓰지 않을 때 기존 CLI가 깨지지 않게 한다."""
    try:
        import psycopg
    except ImportError as error:
        raise DatabaseConnectionError(
            "psycopg가 필요합니다. pip install -r requirements-db.txt를 실행하세요."
        ) from error
    return psycopg.connect(DatabaseSettings.from_env().dsn)
