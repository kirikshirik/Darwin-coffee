"""Offline-демо Фазы 4 — прогноз месяца + «вау»-аналитика. БЕЗ токенов и сети.

  1) Загружает образцы чеков за две недели (DOCUMENTS_WEEK) в БД.
  2) Прогноз месяца: историческая модель (работает на реальных помесячных данных уже
     сейчас) + run-rate по чекам (механика на образцах).
  3) Инсайты: топ по прибыли, прибыльные часы, неделя-к-неделе, рейтинг бариста.

Запуск:
    .venv/bin/python -m backend.analytics.demo
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend import seed
from backend.analytics import forecast, insights
from backend.bot import formatting, metrics
from backend.db import SessionLocal
from backend.integrations.evotor import mapping, sample_data

DEMO_COST_BY_NAME = {
    "Капучино 350": Decimal("77.45"),
    "Латте 250": Decimal("67.82"),
    "Круассан": Decimal("45.00"),
}
TODAY = date.fromisoformat(sample_data.ANALYTICS_TODAY)  # 2026-06-14


def _print_block(title: str, text: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("-" * 64)
    print(text)


def main() -> None:
    print("\n☕ Фаза 4 — offline-демо прогноза и аналитики\n")

    biz_id = seed.seed()
    with SessionLocal() as s:
        mapping.sync_products(s, biz_id, sample_data.PRODUCTS)
        added = mapping.sync_sales(s, biz_id, sample_data.DOCUMENTS_WEEK, DEMO_COST_BY_NAME)
    print(f"Загружено образцов чеков за 2 недели: {added}")

    # 1) Прогноз — историческая модель (без Эвотора, на реальных помесячных данных)
    fc_hist = forecast.forecast_history()  # месяц после последнего в истории (июнь 2026)
    _print_block("ПРОГНОЗ — историческая модель (работает уже сейчас)", formatting.format_forecast(fc_hist))

    # 2) Прогноз — run-rate по чекам текущего месяца (механика на образцах)
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        fc_rr = forecast.forecast_runrate(s, biz, TODAY)
    _print_block(
        "ПРОГНОЗ — run-rate по чекам (механика на игрушечных образцах)",
        formatting.format_forecast(fc_rr) if fc_rr else "нет чеков за текущий месяц",
    )

    # 3) Инсайты по чекам
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        ins = insights.compute(s, biz, TODAY)
    _print_block(f"АНАЛИТИКА (окно 2 недели, today={TODAY:%d.%m.%Y})", formatting.format_insights(ins))

    # Контроль: образцы разобрались
    ok = ins.has_data and bool(ins.top_by_profit) and bool(ins.baristas) and ins.wow is not None
    print("\n" + ("✅ Прогноз и аналитика работают." if ok else "❌ Инсайты пусты — проверь демо."))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
