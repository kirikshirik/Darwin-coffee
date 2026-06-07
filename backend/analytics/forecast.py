"""Прогноз выручки и прибыли месяца (Фаза 4).

Две модели — выбираются по наличию данных:

  • run-rate по чекам — когда есть чеки Эвотора за текущий месяц: экстраполируем
    выручку и COGS по числу прошедших дней, операционку держим фиксированной (она
    помесячная). Самый точный прогноз в середине месяца — killer-фича для владельца.

  • историческая — когда чеков нет (Эвотор не подключён): берём среднее честной
    прибыли/выручки за последние N месяцев накопленной истории (`darwin_data` +
    overlay), плюс «тот же месяц год назад» для контекста. Работает уже сейчас.

Вся прибыль считается тем же честным методом, что и в `bot.metrics`/`honest_report`.
Деньги — Decimal.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from sqlalchemy.orm import Session

from backend import darwin_data
from backend.bot import metrics

ZERO = Decimal("0")
CENT = Decimal("0.01")


@dataclass
class MonthForecast:
    period: date
    method: str
    projected_revenue: Decimal
    projected_net: Decimal
    projected_margin_pct: float
    basis: str
    # детали run-rate (None для исторической модели)
    mtd_revenue: Optional[Decimal] = None
    mtd_net: Optional[Decimal] = None
    days_elapsed: Optional[int] = None
    days_in_month: Optional[int] = None
    # детали исторической модели (None для run-rate)
    low_net: Optional[Decimal] = None
    high_net: Optional[Decimal] = None
    last_year_net: Optional[Decimal] = None
    last_year_revenue: Optional[Decimal] = None


def _q(x) -> Decimal:
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def _margin(net: Decimal, rev: Decimal) -> float:
    return float((net / rev * 100).quantize(Decimal("0.1"))) if rev else 0.0


def _history_periods() -> List[date]:
    return sorted(m["period"] for m in darwin_data.MONTHLY)


def _add_month(d: date) -> date:
    return date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)


def _operating_estimate(period: date) -> Decimal:
    """Фиксированная операционка месяца (аренда, ФОТ, налоги…). Для будущего месяца,
    которого ещё нет в Excel, берём последний известный месяц — фикс. расходы стабильны."""
    hm = metrics.honest_month(period) or metrics.honest_month(metrics.latest_month_period())
    return sum(hm["operating"].values(), ZERO) if hm else ZERO


def forecast_runrate(session: Session, business_id: int, today: date) -> Optional[MonthForecast]:
    """Прогноз месяца по чекам текущего месяца (run-rate). None, если чеков нет."""
    period = date(today.year, today.month, 1)
    dim = monthrange(today.year, today.month)[1]
    elapsed = today.day

    start = datetime(today.year, today.month, 1)
    end = datetime(today.year, today.month, today.day) + timedelta(days=1)
    agg = metrics.sales_aggregate(session, business_id, start, end)
    if agg["checks"] == 0:
        return None

    rev_mtd, cogs_mtd = agg["revenue"], agg["cogs"]
    operating_full = _operating_estimate(period)
    scale = Decimal(dim) / Decimal(elapsed)

    proj_rev = rev_mtd * scale
    proj_cogs = cogs_mtd * scale
    proj_net = proj_rev - proj_cogs - operating_full
    mtd_net = rev_mtd - cogs_mtd - operating_full * Decimal(elapsed) / Decimal(dim)

    return MonthForecast(
        period=period,
        method="run-rate по чекам",
        projected_revenue=_q(proj_rev),
        projected_net=_q(proj_net),
        projected_margin_pct=_margin(proj_rev - proj_cogs - operating_full, proj_rev),
        basis=f"по {elapsed} дн. из {dim}: выручка/COGS экстраполированы, опер. расходы фиксированы",
        mtd_revenue=_q(rev_mtd),
        mtd_net=_q(mtd_net),
        days_elapsed=elapsed,
        days_in_month=dim,
    )


def forecast_history(target_period: Optional[date] = None, lookback: int = 3) -> Optional[MonthForecast]:
    """Прогноз месяца по накопленной истории (среднее за N месяцев). None, если истории нет."""
    periods = _history_periods()
    if not periods:
        return None
    if target_period is None:
        target_period = _add_month(periods[-1])
    target_period = date(target_period.year, target_period.month, 1)

    prior = [p for p in periods if p < target_period][-lookback:] or periods[-lookback:]
    nets = [metrics.monthly_report(p).report.net_profit for p in prior]
    revs = [metrics.monthly_report(p).report.revenue for p in prior]
    proj_net = sum(nets, ZERO) / len(nets)
    proj_rev = sum(revs, ZERO) / len(revs)

    ly = date(target_period.year - 1, target_period.month, 1)
    last_year_net = last_year_rev = None
    if ly in periods:
        lr = metrics.monthly_report(ly).report
        last_year_net, last_year_rev = lr.net_profit, lr.revenue

    labels = ", ".join(metrics._month_label(p) for p in prior)
    return MonthForecast(
        period=target_period,
        method=f"история (среднее {len(prior)} мес)",
        projected_revenue=_q(proj_rev),
        projected_net=_q(proj_net),
        projected_margin_pct=_margin(proj_net, proj_rev),
        basis=f"среднее за {labels}",
        low_net=_q(min(nets)),
        high_net=_q(max(nets)),
        last_year_net=last_year_net,
        last_year_revenue=last_year_rev,
    )


def forecast_month(session: Session, business_id: int, today: date, lookback: int = 3) -> MonthForecast:
    """Лучший доступный прогноз текущего месяца: run-rate по чекам, иначе — по истории."""
    fc = forecast_runrate(session, business_id, today)
    if fc is not None:
        return fc
    return forecast_history(date(today.year, today.month, 1), lookback)
