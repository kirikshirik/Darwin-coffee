"""Живой смоук-тест Облака Эвотор — С РЕАЛЬНЫМ Cloud Token (нужна сеть).

В отличие от demo.py (offline, на образцах) этот скрипт реально ходит в API:
проверяет, что токен/заголовок приняты, и показывает первые данные аккаунта.
Это и есть закрытие блокера №1 («сверить эндпоинты с docs, нужен Cloud Token»).

Запуск:
    .venv/bin/python -m backend.integrations.evotor.live_check

Скрипт НИЧЕГО не пишет в БД — только читает и печатает. Что проверяем глазами:
  • авторизацию: /stores ответил 200, виден ваш магазин;
  • единицы денег: совпадает ли сумма чека с тем, что в кабинете Эвотора.
    Если в кабинете 250 ₽, а тут «25000» — деньги в копейках: поставьте в .env
    EVOTOR_MONEY_IN_KOPECKS=1 (маппинг это учитывает, см. mapping._money).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from backend.financial.profit_calculator import rub
from backend.integrations.evotor import mapping
from backend.integrations.evotor.client import EvotorClient
from backend.integrations.evotor.exceptions import (
    EvotorAPIError,
    EvotorAuthError,
    EvotorConfigError,
)

DAYS_BACK = 7      # за сколько дней тянуть чеки
SAMPLE = 5         # сколько строк показать в примерах


def _store_id(store: dict) -> str | None:
    return store.get("id") or store.get("uuid")


async def run() -> None:
    print("\n☕ Эвотор — ЖИВАЯ проверка токена (реальный API)\n")
    async with EvotorClient.from_env() as evotor:
        # 1) Авторизация + список магазинов
        stores = await evotor.get_stores()
        print(f"✅ Авторизация принята. Магазинов в аккаунте: {len(stores)}")
        for s in stores:
            print(f"  • {s.get('name', '(без имени)')}  id={_store_id(s)}")
        if not stores:
            print("\n⚠️ Магазинов нет — проверьте, что токен от нужного аккаунта.")
            return

        store_id = _store_id(stores[0])
        print(f"\nРаботаем с первым магазином: id={store_id}")

        # 2) Товары
        raw_products = await evotor.get_products(store_id)
        print(f"\nТоваров в каталоге: {len(raw_products)}")
        for p in raw_products[:SAMPLE]:
            mp = mapping.map_product(p, business_id=1)
            print(f"  • {mp.name:<24} цена {rub(mp.sell_price):>10}")

        # 3) Чеки продаж за последние DAYS_BACK дней
        until = datetime.utcnow()
        since = until - timedelta(days=DAYS_BACK)
        raw_sales = await evotor.get_sales(store_id, since, until)
        receipts = [
            r for raw in raw_sales
            if (r := mapping.map_receipt(raw, business_id=1)) is not None
        ]
        print(
            f"\nЧеков продаж (SELL) за {DAYS_BACK} дн.: {len(receipts)} "
            f"(из {len(raw_sales)} документов)"
        )

        total = sum((r.total_sum for r in receipts), Decimal("0"))
        for r in receipts[:SAMPLE]:
            print(f"  • {r.sold_at:%Y-%m-%d %H:%M}  {r.payment_type or '—':<8} итог {rub(r.total_sum)}")
        if receipts:
            print(f"\nВыручка за период: {rub(total)}")
            print(
                "👉 Сверьте эту сумму с кабинетом Эвотора. Расходится в 100 раз → "
                "деньги в копейках, поставьте EVOTOR_MONEY_IN_KOPECKS=1 в .env."
            )
        else:
            print("ℹ️ Чеков за период нет — попробуйте увеличить DAYS_BACK или продать тестовый чек.")

    print("\n✅ Готово. Токен рабочий — можно подключать загрузку в БД (seed/sync) и бота.")


def main() -> None:
    try:
        asyncio.run(run())
    except EvotorConfigError as e:
        raise SystemExit(f"❌ Конфиг: {e}")
    except EvotorAuthError as e:
        raise SystemExit(
            f"❌ Авторизация отклонена (401/403): {e}\n"
            "   Чаще всего — не тот заголовок. Для Cloud Token нужен X-Authorization "
            "(сырой токен); для OAuth — EVOTOR_AUTH_HEADER=Authorization, EVOTOR_AUTH_SCHEME=Bearer."
        )
    except EvotorAPIError as e:
        raise SystemExit(f"❌ Ошибка API Эвотора (status={e.status}): {e}\n   Тело: {e.body}")


if __name__ == "__main__":
    main()
