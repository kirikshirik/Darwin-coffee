"""Подключение к БД.

По умолчанию — локальный SQLite, чтобы стартовать без Docker/PostgreSQL.
На проде задаётся переменная окружения:
    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/darwin
SQLAlchemy позволяет сменить БД без правок моделей.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "darwin.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

_is_sqlite = DATABASE_URL.startswith("sqlite")
# check_same_thread=False — бот читает, синк/планировщик пишут (разные потоки/процессы).
# Безопасность конкурентного доступа обеспечивает WAL + busy_timeout (см. ниже).
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=_connect_args)


if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        """WAL: 1 писатель + много читателей одновременно (бот + синк на одном VPS).

        busy_timeout — ждать снятия блокировки вместо мгновенной ошибки
        «database is locked». synchronous=NORMAL — безопасно при WAL и быстрее.
        """
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Создать все таблицы (для MVP вместо Alembic-миграций)."""
    from backend.models import Base

    Base.metadata.create_all(engine)
