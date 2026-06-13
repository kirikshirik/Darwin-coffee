"""Alembic-окружение «Дарвина».

URL БД берём не из alembic.ini, а из backend.db — там единая логика:
DATABASE_URL из env (Neon/Render postgresql:// нормализуется в psycopg-драйвер)
с фолбэком на локальный SQLite. Так миграции всегда идут в ту же БД, что и приложение.
"""
from logging.config import fileConfig

from sqlalchemy import pool

from alembic import context

from backend.db import DATABASE_URL
from backend.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline-режим: генерирует SQL без подключения к БД (alembic upgrade --sql)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online-режим: обычный запуск миграций по подключению."""
    from sqlalchemy import create_engine

    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
