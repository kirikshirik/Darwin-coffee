"""Offline-демо Telegram-бота — БЕЗ токена бота и без сети.

Прогоняет весь конвейер отчётов так же, как это сделает бот:
  1) сверяет, что помесячный честный P&L совпадает с контролем honest_report (386 821 ₽);
  2) загружает ОБРАЗЦЫ чеков Эвотора в БД (mapping.sync_*) — проверка сквозного пути
     Эвотор → БД → metrics → текст;
  3) печатает готовые тексты кнопок (Месяц, Вчера-по-образцам, Товары, Расходы).

Запуск:
    .venv/bin/python -m backend.bot.demo

Тексты — в HTML parse_mode (теги <b>/<i> увидит Telegram); тут печатаем как есть.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend import darwin_data, seed
from backend.bot import formatting, metrics, reports
from backend.db import SessionLocal
from backend.financial.profit_calculator import rub
from backend.integrations.evotor import mapping, sample_data

# Иллюстративная себестоимость порции (в реале — из cost_reference по объёму стакана).
DEMO_COST_BY_NAME = {
    "Капучино 350": Decimal("77.45"),
    "Латте 250": Decimal("67.82"),
    "Круассан": Decimal("45.00"),
}
SAMPLE_DAY = date(2026, 6, 7)  # дата в образцах документов Эвотора
# = ИТОГО из backend.honest_report. Если honest-логика поменяется — сверить (metrics.honest_month).
HONEST_ANNUAL_CONTROL = Decimal("391520")


def _check_honest_annual() -> None:
    total = sum(
        (metrics.monthly_report(m["period"]).report.net_profit for m in darwin_data.MONTHLY),
        Decimal("0"),
    )
    ok = total == HONEST_ANNUAL_CONTROL
    print(f"1) Честная годовая прибыль (сумма по месяцам): {rub(total)} "
          f"{'✅' if ok else '❌ ожидалось ' + rub(HONEST_ANNUAL_CONTROL)}")
    if not ok:
        raise SystemExit("❌ Метрики разошлись с honest_report — проверь metrics.honest_month.")


def _ingest_samples() -> int:
    """Засеять БД и загрузить образцы чеков Эвотора (сквозной путь)."""
    biz_id = seed.seed()
    with SessionLocal() as s:
        mapping.sync_products(s, biz_id, sample_data.PRODUCTS)
        added = mapping.sync_sales(s, biz_id, sample_data.DOCUMENTS, DEMO_COST_BY_NAME)
    return added


def _print_block(title: str, text: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("-" * 64)
    print(text)


def main() -> None:
    print("\n☕ Бот «Дарвин» — offline-демо отчётов (без токена бота)\n")

    _check_honest_annual()

    added = _ingest_samples()
    print(f"2) Загружено образцов чеков Эвотора в БД: {added} (sync_products + sync_sales) ✅")

    # 3) Тексты кнопок
    _print_block(
        "МЕСЯЦ — честный P&L из Excel (последний месяц, работает без Эвотора)",
        formatting.format_period(metrics.monthly_report()),
    )
    _print_block("МЕСЯЦ через кнопку (текущий месяц по чекам, если они есть)", reports.month_text())
    _print_block(
        f"ВЧЕРА → день образцов {SAMPLE_DAY:%d.%m.%Y} (сквозной путь Эвотор→БД→отчёт)",
        formatting.format_period(_sample_day_report()),
    )
    _print_block("ТОВАРЫ (топ по образцам)", formatting.format_top(_sample_day_report()))
    _print_block("РАСХОДЫ (последний месяц)", reports.expenses_text())

    print("\n✅ Конвейер отчётов работает. Останется задать TELEGRAM_BOT_TOKEN и запустить bot.main.")


def _sample_day_report():
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        return metrics.day_report(s, biz, SAMPLE_DAY, label=f"День образцов · {SAMPLE_DAY:%d.%m.%Y}")


if __name__ == "__main__":
    main()
