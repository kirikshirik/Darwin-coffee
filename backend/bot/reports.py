"""Сборка текстов отчётов: БД → metrics → formatting.

Один слой и для хендлеров бота, и для планировщика. Каждая функция сама открывает
сессию БД и возвращает готовую строку (HTML). `today` можно передать явно (для
тестов/демо); по умолчанию — текущая дата.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from backend.analytics import forecast, insights
from backend.bot import formatting, metrics
from backend.db import SessionLocal


def format_start_text() -> str:
    return formatting.format_start()


def today_text(today: Optional[date] = None) -> str:
    today = today or date.today()
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        pr = metrics.day_report(s, biz, today, label=f"Сегодня · {today:%d.%m.%Y}")
    return formatting.format_period(pr)


def yesterday_text(today: Optional[date] = None) -> str:
    today = today or date.today()
    y = today - timedelta(days=1)
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        pr = metrics.day_report(s, biz, y, label=f"Вчера · {y:%d.%m.%Y}")
    return formatting.format_period(pr)


def week_text(today: Optional[date] = None) -> str:
    today = today or date.today()
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        pr = metrics.week_report(s, biz, today)
    return formatting.format_period(pr)


def month_text(today: Optional[date] = None) -> str:
    """Текущий месяц по чекам Эвотора; если чеков нет — честный P&L из Excel (последний месяц)."""
    today = today or date.today()
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        pr = metrics.month_to_date_report(s, biz, today)
        if not pr.has_data:
            pr = metrics.monthly_report()
    return formatting.format_period(pr)


def products_text(today: Optional[date] = None) -> str:
    today = today or date.today()
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        pr = metrics.month_to_date_report(s, biz, today)
    return formatting.format_top(pr)


def expenses_text() -> str:
    period, rows, total = metrics.expenses_breakdown()
    return formatting.format_expenses(period, rows, total)


def forecast_text(today: Optional[date] = None) -> str:
    today = today or date.today()
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        fc = forecast.forecast_month(s, biz, today)
    return formatting.format_forecast(fc)


def insights_text(today: Optional[date] = None) -> str:
    today = today or date.today()
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        ins = insights.compute(s, biz, today)
    return formatting.format_insights(ins)


def morning_text(today: Optional[date] = None) -> str:
    """Утренняя сводка: вчера по чекам (или честный месяц, если чеков нет) + прогноз месяца."""
    today = today or date.today()
    y = today - timedelta(days=1)
    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        pr = metrics.day_report(s, biz, y, label=f"Вчера · {y:%d.%m.%Y}")
        fc = forecast.forecast_month(s, biz, today)
        if pr.has_data:
            base = formatting.format_period(pr)
        else:
            # Чеков ещё нет (Эвотор не подключён) — headline-ценность на реальных данных.
            base = formatting.format_period(metrics.monthly_report())
            base += "\n\n<i>Дневной отчёт включится автоматически после подключения Эвотора.</i>"
    return base + "\n\n" + formatting.format_forecast_line(fc)
