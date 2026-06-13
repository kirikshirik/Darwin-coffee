"""Маппинг Эвотора: кассир чека и рейтинг бариста.

Кассир чека — close_user_id документа (UUID сотрудника из /employees);
user_id документа — это id аккаунта, один на все чеки (проверено на живых данных).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from backend.analytics import insights
from backend.db import SessionLocal
from backend.integrations.evotor import mapping, sample_data
from backend.models import Receipt


@pytest.fixture()
def fresh_business(seeded_db):
    """Чистая пересеянная БД на каждый тест (образцы чеков не накапливаются)."""
    from backend import seed

    return seed.seed()


def test_cashier_is_close_user_id(fresh_business):
    with SessionLocal() as s:
        mapping.sync_products(s, fresh_business, sample_data.PRODUCTS)
        added = mapping.sync_sales(s, fresh_business, sample_data.DOCUMENTS)
        assert added == sample_data.EXPECTED_SALES_COUNT
        cashiers = set(s.scalars(select(Receipt.cashier)))
        assert cashiers == {sample_data.EMP_ANNA, sample_data.EMP_IGOR}


def test_barista_names_resolved(fresh_business):
    with SessionLocal() as s:
        mapping.sync_products(s, fresh_business, sample_data.PRODUCTS)
        mapping.sync_employees(s, fresh_business, sample_data.EMPLOYEES)
        mapping.sync_sales(s, fresh_business, sample_data.DOCUMENTS_WEEK)
        ins = insights.compute(s, fresh_business, date.fromisoformat(sample_data.ANALYTICS_TODAY))
        names = {b.name for b in ins.baristas}
        assert names == {"Анна Соколова", "Игорь Ветров"}


def test_unknown_cashier_falls_back_to_short_id(fresh_business):
    """Без синка сотрудников рейтинг не падает — показывает короткий ID, не UUID-простыню."""
    with SessionLocal() as s:
        mapping.sync_products(s, fresh_business, sample_data.PRODUCTS)
        mapping.sync_sales(s, fresh_business, sample_data.DOCUMENTS)
        ins = insights.compute(s, fresh_business, date(2026, 6, 7))
        assert ins.baristas and all(b.name.startswith("Сотрудник ") for b in ins.baristas)


def test_cashier_healed_on_resync(fresh_business):
    """Чеки, загруженные до фикса (cashier = id аккаунта), лечатся при повторном синке."""
    legacy_docs = []
    for d in sample_data.DOCUMENTS:
        d = dict(d)
        d.pop("close_user_id", None)  # как выглядел маппинг до фикса
        legacy_docs.append(d)

    with SessionLocal() as s:
        mapping.sync_products(s, fresh_business, sample_data.PRODUCTS)
        mapping.sync_sales(s, fresh_business, legacy_docs)
        cashiers = set(s.scalars(select(Receipt.cashier)))
        assert cashiers == {sample_data.ACCOUNT_USER_ID}

        added = mapping.sync_sales(s, fresh_business, sample_data.DOCUMENTS)
        assert added == 0  # дубли не плодим
        cashiers = set(s.scalars(select(Receipt.cashier)))
        assert cashiers == {sample_data.EMP_ANNA, sample_data.EMP_IGOR}
