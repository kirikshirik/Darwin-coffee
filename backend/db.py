"""Подключение к БД.

По умолчанию — локальный SQLite, чтобы стартовать без Docker/PostgreSQL.
На проде задаётся переменная окружения:
    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/darwin
SQLAlchemy позволяет сменить БД без правок моделей.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "darwin.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Создать все таблицы (для MVP вместо Alembic-миграций)."""
    from backend.models import Base

    Base.metadata.create_all(engine)
