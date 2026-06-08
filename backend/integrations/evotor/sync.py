"""Синхронизация Эвотор → БД: товары и чеки продаж (закрывает шаг №1 README).

Запуск:
    .venv/bin/python -m backend.integrations.evotor.sync            # последние 30 дней
    .venv/bin/python -m backend.integrations.evotor.sync --days 60

Требует EVOTOR_CLOUD_TOKEN (.env) и засеянный бизнес (backend.seed).
Идемпотентно: товары — апсерт по uuid, чеки — дедуп по receipt_uuid (повторный
запуск не плодит дубли, можно ставить по расписанию). В БД пишет только этот шаг;
бот после него отвечает на живых данных (Сегодня/Неделя/Товары/Аналитика/Прогноз).

COGS по чекам: точного сопоставления рецептов к именам товаров Эвотора пока нет
(это следующий шаг — маржа по напиткам). До него себестоимость позиции оцениваем
как долю цены по реальному food cost кофейни (actuals_data.food_cost_ratio() ≈ 26.7%),
чтобы бот показывал осмысленную валовую прибыль, а не 100% маржу. Переопределяется
флагом --cogs-ratio.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select

from backend import actuals_data
from backend.bot import metrics
from backend.db import SessionLocal
from backend.integrations.evotor import mapping
from backend.integrations.evotor.client import EvotorClient
from backend.integrations.evotor.exceptions import (
    EvotorAPIError,
    EvotorAuthError,
    EvotorConfigError,
)
from backend.models import Business, Product


def _store_id(store: dict) -> Optional[str]:
    return store.get("id") or store.get("uuid")


async def _pull(days: int):
    """Сетевая часть: тянем магазин, товары и чеки за N дней (без записи в БД)."""
    async with EvotorClient.from_env() as evotor:
        stores = await evotor.get_stores()
        if not stores:
            raise SystemExit("❌ В аккаунте Эвотора нет магазинов.")
        store = stores[0]
        sid = _store_id(store)
        raw_products = await evotor.get_products(sid)
        until = datetime.utcnow()
        since = until - timedelta(days=days)
        raw_sales = await evotor.get_sales(sid, since, until)
    return store, raw_products, raw_sales


def sync(days: int = 30, ratio: Optional[Decimal] = None) -> None:
    store, raw_products, raw_sales = asyncio.run(_pull(days))
    cogs_ratio = actuals_data.food_cost_ratio() if ratio is None else ratio

    with SessionLocal() as session:
        biz_id = metrics.get_business_id(session)

        biz = session.get(Business, biz_id)
        if biz is not None and not biz.evotor_store_uuid:
            biz.evotor_store_uuid = _store_id(store)

        n_prod = mapping.sync_products(session, biz_id, raw_products)

        # Прокси COGS: себестоимость позиции = цена × доля food cost (см. docstring).
        products = session.scalars(
            select(Product).where(Product.business_id == biz_id)
        ).all()
        cost_by_name = {p.name: p.sell_price * cogs_ratio for p in products if p.sell_price}

        n_sales = mapping.sync_sales(session, biz_id, raw_sales, cost_by_name)
        session.commit()

    print(f"✅ Синхронизация Эвотора завершена (магазин «{store.get('name', '?')}»):")
    print(f"   товаров обработано:  {n_prod}")
    print(f"   новых чеков продаж:  {n_sales} (из {len(raw_sales)} документов за {days} дн.)")
    print(f"   себестоимость позиций: прокси {cogs_ratio * 100:.1f}% от цены (реальный food cost)")
    print("\nГотово. Бот теперь отвечает на живых данных: Сегодня · Неделя · Товары · Аналитика · Прогноз.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Синхронизация Эвотор → БД (товары + чеки)")
    ap.add_argument("--days", type=int, default=30, help="за сколько дней тянуть чеки (по умолч. 30)")
    ap.add_argument(
        "--cogs-ratio", type=str, default=None,
        help="переопределить долю себестоимости, напр. 0.27 (по умолч. — реальный food cost)",
    )
    args = ap.parse_args()
    ratio = Decimal(args.cogs_ratio) if args.cogs_ratio else None
    try:
        sync(days=args.days, ratio=ratio)
    except EvotorConfigError as e:
        raise SystemExit(f"❌ Конфиг: {e}")
    except EvotorAuthError as e:
        raise SystemExit(f"❌ Авторизация отклонена (401/403): {e}")
    except EvotorAPIError as e:
        raise SystemExit(f"❌ Ошибка API Эвотора (status={e.status}): {e}")


if __name__ == "__main__":
    main()
