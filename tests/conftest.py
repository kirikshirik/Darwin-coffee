"""Тестовая БД — отдельный SQLite во временной папке.

DATABASE_URL надо задать ДО первого импорта backend.db (engine создаётся при
импорте модуля), поэтому env выставляется на уровне модуля conftest, а не в фикстуре.
Локальная darwin.db и прод-Postgres тестами не затрагиваются.
"""
import os
import tempfile

_TMPDIR = tempfile.mkdtemp(prefix="darwin-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"

import pytest


@pytest.fixture(scope="session")
def seeded_db():
    """БД с реальными данными «Дарвина» (эквивалент python -m backend.seed)."""
    from backend import seed

    seed.seed()
