"""Программный запуск Alembic-миграций (вызывается на старте бота).

Особый случай — БД, созданные ДО Alembic через `Base.metadata.create_all`
(локальные SQLite и прод-Neon с живыми чеками): схема в них уже есть, но нет
таблицы alembic_version. Такие помечаем baseline-ревизией (stamp), и дальше
к ним применяются только новые миграции — ничего не пересоздаётся.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from backend.db import engine

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
BASELINE_REVISION = "0001"


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    # пути задаём абсолютно — бот может стартовать из любого cwd (systemd, Render)
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def upgrade_to_head() -> None:
    """Довести схему БД до актуальной ревизии (идемпотентно)."""
    cfg = _config()
    insp = inspect(engine)
    if insp.has_table("businesses") and not insp.has_table("alembic_version"):
        log.info("БД создана до Alembic — помечаю baseline-ревизией %s", BASELINE_REVISION)
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")


def stamp_head() -> None:
    """Пометить свежесозданную (create_all) схему как актуальную — для seed()."""
    command.stamp(_config(), "head")
