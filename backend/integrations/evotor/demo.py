"""Offline-демо интеграции с Эвотором — БЕЗ токена и без сети.

Прогоняет маппинг (sample_data → доменные модели), печатает результат и сверяет
контрольные суммы. Это «проверено настолько, насколько возможно без Cloud Token»:
эндпоинты/заголовки сверены с докой (см. client.py), а разбор ответа — здесь.

Запуск:
    .venv/bin/python -m backend.integrations.evotor.demo

Когда появится Cloud Token — те же функции маппинга используются на реальных
ответах EvotorClient (см. блок «С реальным токеном» внизу файла).
"""
from __future__ import annotations

from decimal import Decimal

from backend.financial.profit_calculator import rub
from backend.integrations.evotor import mapping, sample_data

BIZ_ID = 1

# Иллюстративная себестоимость порции по имени (в реале — из cost_reference по объёму).
DEMO_COST_BY_NAME = {
    "Капучино 350": Decimal("77.45"),
    "Латте 250": Decimal("67.82"),
    "Круассан": Decimal("45.00"),
}


def main() -> None:
    print("\n☕ Эвотор — offline-демо маппинга (без токена, на образцах ответа)\n")

    # 1) Товары
    products = [mapping.map_product(p, BIZ_ID) for p in sample_data.PRODUCTS]
    print(f"Товаров получено: {len(products)}")
    for p in products:
        print(f"  • {p.name:<16} цена {rub(p.sell_price):>10}  uuid={p.evotor_uuid}")

    # 2) Чеки продаж (возврат PAYBACK должен отсеяться)
    receipts = [
        r
        for raw in sample_data.DOCUMENTS
        if (r := mapping.map_receipt(raw, BIZ_ID, DEMO_COST_BY_NAME)) is not None
    ]
    print(f"\nЧеков продаж (SELL): {len(receipts)} "
          f"(из {len(sample_data.DOCUMENTS)} документов; возвраты отфильтрованы)")

    total_rev = Decimal("0")
    total_profit = Decimal("0")
    for r in receipts:
        total_rev += r.total_sum
        rprofit = sum((i.profit for i in r.items), Decimal("0"))
        total_profit += rprofit
        print(f"\n  Чек {r.receipt_uuid} | {r.sold_at:%Y-%m-%d %H:%M} | "
              f"{r.payment_type} | итог {rub(r.total_sum)}")
        for i in r.items:
            print(f"     {i.quantity} × {rub(i.price)} = выручка {rub(i.revenue)}, "
                  f"себест. {rub(i.cost)}, прибыль {rub(i.profit)}")

    print("\n" + "-" * 60)
    print(f"Выручка по чекам:  {rub(total_rev)}")
    print(f"Валовая прибыль:   {rub(total_profit)} "
          f"({(total_profit / total_rev * 100):.1f}% маржа)" if total_rev else "")

    # 3) Контроль
    ok_count = len(receipts) == sample_data.EXPECTED_SALES_COUNT
    ok_rev = total_rev == Decimal(sample_data.EXPECTED_REVENUE)
    print("\nКонтроль:")
    print(f"  чеков продаж = {sample_data.EXPECTED_SALES_COUNT}: {'✅' if ok_count else '❌'}")
    print(f"  выручка = {rub(Decimal(sample_data.EXPECTED_REVENUE))}: {'✅' if ok_rev else '❌'}")
    if ok_count and ok_rev:
        print("\n✅ МАППИНГ РАБОТАЕТ. Готово к подключению реального Cloud Token.")
    else:
        raise SystemExit("❌ Маппинг разошёлся с контролем — проверь mapping.py / sample_data.py")

    # --- С реальным токеном (когда снимут блокер №1) -----------------------------
    # from datetime import datetime, timedelta
    # from backend.integrations.evotor.client import EvotorClient
    # import asyncio
    # async def pull():
    #     async with EvotorClient.from_env() as evotor:
    #         stores = await evotor.get_stores()
    #         store_id = stores[0]["id"]
    #         raw_products = await evotor.get_products(store_id)
    #         since = datetime.utcnow() - timedelta(days=1)
    #         raw_sales = await evotor.get_sales(store_id, since, datetime.utcnow())
    #         # mapping.sync_products(session, biz_id, raw_products)
    #         # mapping.sync_sales(session, biz_id, raw_sales, cost_by_name)
    # asyncio.run(pull())


if __name__ == "__main__":
    main()
