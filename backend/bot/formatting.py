"""Рендеринг отчётов в текст Telegram (HTML parse_mode).

Чистый модуль: принимает PeriodReport/данные из metrics, возвращает строки. Не
импортирует aiogram — поэтому тексты можно проверять offline (bot/demo.py).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.analytics.forecast import MonthForecast
from backend.analytics.insights import Insights
from backend.bot.metrics import PeriodReport, _month_label
from backend.financial.profit_calculator import rub

BRAND = "☕ <b>Дарвин</b>"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _signed(pct) -> str:
    if pct is None:
        return ""
    return f"({'+' if pct >= 0 else ''}{pct:.1f}%)"


def format_period(pr: PeriodReport) -> str:
    """Главный отчёт за период (день/неделя/месяц)."""
    r = pr.report
    lines = [f"{BRAND} — {pr.label}", f"<i>{pr.source}</i>", ""]

    if pr.from_receipts and pr.checks_count == 0:
        lines.append("Нет чеков за период.")
        lines.append("Подключите Эвотор (Cloud Token) — отчёт заполнится автоматически.")
        return "\n".join(lines)

    lines.append(f"Выручка: <b>{rub(r.revenue)}</b>")
    cogs_note = " <i>(оценка по «Прочее»)</i>" if pr.cogs_is_proxy else ""
    lines.append(f"Себестоимость: {rub(r.cogs)}{cogs_note}")
    lines.append(f"Валовая прибыль: {rub(r.gross_profit)} ({_pct(r.gross_margin_pct)})")
    lines.append(f"Опер. расходы: {rub(r.operating_expenses)}")
    lines.append(f"Чистая прибыль: <b>{rub(r.net_profit)}</b> ({_pct(r.net_margin_pct)})")

    if pr.from_receipts:
        lines.append("")
        lines.append(f"Чеков: {pr.checks_count}   Средний чек: {rub(pr.avg_check)}")
        if pr.top_products:
            lines.append("")
            lines.append("<b>Топ товаров:</b>")
            lines.extend(_format_top_lines(pr))

    if r.warnings:
        lines.append("")
        lines.append("⚠️ " + "\n⚠️ ".join(r.warnings))

    return "\n".join(lines)


def _format_top_lines(pr: PeriodReport, limit: int = 5) -> list:
    out = []
    for i, t in enumerate(pr.top_products[:limit], 1):
        qty = f"{t.qty:.0f}".rstrip()
        out.append(f"{i}. {t.name} — {qty} шт, {rub(t.revenue)} (приб. {rub(t.profit)})")
    return out


def format_top(pr: PeriodReport) -> str:
    """Отдельный экран «Товары»."""
    if pr.from_receipts and pr.checks_count == 0:
        return f"{BRAND} — Товары\n\nНет данных по чекам. Подключите Эвотор."
    if not pr.top_products:
        return f"{BRAND} — Товары\n\nЗа период {pr.label} продаж не найдено."
    lines = [f"{BRAND} — Топ товаров ({pr.label})", ""]
    lines.extend(_format_top_lines(pr, limit=10))
    return "\n".join(lines)


def format_expenses(period: date, rows: list, total: Decimal) -> str:
    """Экран «Расходы»: помесячная разбивка (честная — с COGS и реальным ФОТ)."""
    from backend.bot.metrics import _month_label  # локальный импорт, чтобы не плодить API

    lines = [f"{BRAND} — Расходы ({_month_label(period)})", "<i>Excel помесячно · честный учёт</i>", ""]
    for name, amount in rows:
        lines.append(f"• {name}: {rub(amount)}")
    lines.append("")
    lines.append(f"Итого расходов: <b>{rub(total)}</b>")
    return "\n".join(lines)


def format_forecast(fc: MonthForecast) -> str:
    """Экран «Прогноз» месяца."""
    lines = [f"{BRAND} — Прогноз: {_month_label(fc.period)}", f"<i>{fc.method}</i>", ""]
    lines.append(f"Прогноз выручки: <b>{rub(fc.projected_revenue)}</b>")
    lines.append(
        f"Прогноз чистой прибыли: <b>{rub(fc.projected_net)}</b> ({_pct(fc.projected_margin_pct)})"
    )

    if fc.mtd_revenue is not None:  # run-rate — расписываем арифметику для наглядности
        scale = fc.days_in_month / fc.days_elapsed
        lines.append("")
        lines.append(f"<b>Как считаем</b> ({fc.days_elapsed} из {fc.days_in_month} дн., ×{scale:.2f}):")
        lines.append(f"• Выручка: {rub(fc.mtd_revenue)} → {rub(fc.projected_revenue)}")
        lines.append(f"• Себестоимость: {rub(fc.mtd_cogs)} → {rub(fc.projected_cogs)}")
        lines.append(f"• Опер. расходы (фикс/мес): {rub(fc.operating)}")
        lines.append(
            f"• Прибыль: {rub(fc.projected_revenue)} − {rub(fc.projected_cogs)} − "
            f"{rub(fc.operating)} = <b>{rub(fc.projected_net)}</b>"
        )
        lines.append("")
        lines.append(
            f"Факт за {fc.days_elapsed}/{fc.days_in_month} дн.: "
            f"выручка {rub(fc.mtd_revenue)}, прибыль {rub(fc.mtd_net)}"
        )
    else:  # историческая модель
        lines.append(f"<i>Основа: {fc.basis}</i>")
        if fc.low_net is not None:
            lines.append("")
            lines.append(f"Разброс прибыли по месяцам: {rub(fc.low_net)} … {rub(fc.high_net)}")
        if fc.last_year_net is not None:
            lines.append(
                f"Год назад: прибыль {rub(fc.last_year_net)}, выручка {rub(fc.last_year_revenue)}"
            )
    return "\n".join(lines)


def format_forecast_line(fc: MonthForecast) -> str:
    """Однострочный прогноз — для утренней сводки."""
    return f"📈 Прогноз прибыли месяца ({_month_label(fc.period)}): <b>{rub(fc.projected_net)}</b>"


def format_insights(ins: Insights) -> str:
    """Экран «Аналитика»: неделя-к-неделе, топ по прибыли, часы, бариста."""
    if not ins.has_data:
        return f"{BRAND} — Аналитика\n\nНет чеков за период. Подключите Эвотор."

    lines = [f"{BRAND} — Аналитика ({ins.window_label})", ""]
    if ins.wow:
        w = ins.wow
        lines.append(
            f"<b>Неделя к неделе</b> "
            f"({w.last_start:%d.%m}–{w.last_end:%d.%m} vs {w.this_start:%d.%m}–{w.this_end:%d.%m}):"
        )
        lines.append(
            f"Выручка: {rub(w.last_revenue)} → {rub(w.this_revenue)} {_signed(w.revenue_change_pct)}"
        )
        lines.append(
            f"Прибыль: {rub(w.last_net)} → {rub(w.this_net)} {_signed(w.net_change_pct)}"
        )
        lines.append("")
    if ins.top_by_profit:
        lines.append("<b>Топ по прибыли:</b>")
        for i, t in enumerate(ins.top_by_profit[:5], 1):
            lines.append(f"{i}. {t.name} — приб. {rub(t.profit)} (выручка {rub(t.revenue)})")
        lines.append("")
    if ins.hours:
        lines.append("<b>Самые прибыльные часы:</b>")
        for s in ins.hours[:3]:
            lines.append(f"{s.hour:02d}:00–{s.hour + 1:02d}:00 — приб. {rub(s.profit)} ({s.checks} чек.)")
        lines.append("")
    if ins.baristas:
        lines.append("<b>Рейтинг бариста:</b>")
        for i, b in enumerate(ins.baristas, 1):
            lines.append(
                f"{i}. {b.name} — выручка {rub(b.revenue)}, приб. {rub(b.profit)} ({b.checks} чек.)"
            )
    return "\n".join(lines).rstrip()


def format_start() -> str:
    return (
        f"{BRAND} — аналитика реальной прибыли\n\n"
        "Эвотор показывает выручку. Я показываю, сколько вы реально заработали "
        "после себестоимости, аренды, зарплат и налогов.\n\n"
        "Кнопки ниже: Сегодня · Вчера · Неделя · Месяц · Товары · Расходы · "
        "Прогноз · Аналитика.\n"
        "Команда /dashboard — прислать полную ops-панель файлом (для владельца).\n"
        "Каждое утро пришлю сводку за вчера + прогноз прибыли месяца автоматически."
    )
