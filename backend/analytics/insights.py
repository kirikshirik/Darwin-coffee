"""«Вау»-аналитика по чекам Эвотора (Фаза 4):
топ товаров по прибыли · самые прибыльные часы · неделя-к-неделе · рейтинг бариста.

Чистый модуль над БД (читает receipts/receipt_items). Без чеков (Эвотор не подключён)
возвращает has_data=False. Прибыль за неделю считается через `bot.metrics` (ProfitCalculator).
Деньги — Decimal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.bot import metrics
from backend.bot.metrics import TopProduct
from backend.models import Receipt

ZERO = Decimal("0")


@dataclass
class HourStat:
    hour: int
    revenue: Decimal
    profit: Decimal
    checks: int


@dataclass
class BaristaStat:
    name: str
    revenue: Decimal
    profit: Decimal
    checks: int


@dataclass
class WeekOverWeek:
    this_revenue: Decimal
    last_revenue: Decimal
    this_net: Decimal
    last_net: Decimal
    this_start: date          # границы недель — те же, что суммирует week_report
    this_end: date
    last_start: date
    last_end: date

    @staticmethod
    def _change(now: Decimal, prev: Decimal) -> Optional[float]:
        if not prev:
            return None
        return float((now - prev) / prev * 100)

    @property
    def revenue_change_pct(self) -> Optional[float]:
        return self._change(self.this_revenue, self.last_revenue)

    @property
    def net_change_pct(self) -> Optional[float]:
        return self._change(self.this_net, self.last_net)


@dataclass
class Insights:
    window_label: str
    checks: int
    top_by_profit: List[TopProduct] = field(default_factory=list)
    hours: List[HourStat] = field(default_factory=list)
    baristas: List[BaristaStat] = field(default_factory=list)
    wow: Optional[WeekOverWeek] = None

    @property
    def has_data(self) -> bool:
        return self.checks > 0


def compute(session: Session, business_id: int, today: date, window_days: int = 14) -> Insights:
    """Инсайты за последние window_days дней (по умолчанию 2 недели — для сравнения)."""
    end = datetime(today.year, today.month, today.day) + timedelta(days=1)
    start = end - timedelta(days=window_days)
    receipts = session.scalars(
        select(Receipt).where(
            Receipt.business_id == business_id,
            Receipt.sold_at >= start,
            Receipt.sold_at < end,
        )
    ).all()

    window_label = f"{start.date():%d.%m}–{(end - timedelta(days=1)).date():%d.%m}"
    if not receipts:
        return Insights(window_label=window_label, checks=0)

    prod: Dict[str, List[Decimal]] = {}     # name -> [qty, revenue, profit]
    hours: Dict[int, List] = {}             # hour -> [revenue, profit, checks]
    bar: Dict[str, List] = {}               # cashier -> [revenue, profit, checks]

    for r in receipts:
        r_profit = sum((i.profit for i in r.items), ZERO)
        hc = hours.setdefault(r.sold_at.hour, [ZERO, ZERO, 0])
        hc[0] += r.total_sum
        hc[1] += r_profit
        hc[2] += 1

        name = r.cashier or "(не указан)"
        bc = bar.setdefault(name, [ZERO, ZERO, 0])
        bc[0] += r.total_sum
        bc[1] += r_profit
        bc[2] += 1

        for i in r.items:
            pname = i.product.name if i.product else "(прочее)"
            cell = prod.setdefault(pname, [ZERO, ZERO, ZERO])
            cell[0] += i.quantity
            cell[1] += i.revenue
            cell[2] += i.profit

    top_by_profit = sorted(
        (TopProduct(n, v[0], v[1], v[2]) for n, v in prod.items()),
        key=lambda t: t.profit,
        reverse=True,
    )
    hour_stats = sorted(
        (HourStat(h, v[0], v[1], v[2]) for h, v in hours.items()),
        key=lambda s: s.profit,
        reverse=True,
    )
    barista_stats = sorted(
        (BaristaStat(n, v[0], v[1], v[2]) for n, v in bar.items()),
        key=lambda s: s.revenue,
        reverse=True,
    )

    # Неделя к неделе: эта неделя (today-6..today) vs прошлая (today-13..today-7).
    this_w = metrics.week_report(session, business_id, today)
    last_w = metrics.week_report(session, business_id, today - timedelta(days=7))
    wow = None
    if this_w.checks_count or last_w.checks_count:
        wow = WeekOverWeek(
            this_revenue=this_w.report.revenue,
            last_revenue=last_w.report.revenue,
            this_net=this_w.report.net_profit,
            last_net=last_w.report.net_profit,
            this_start=this_w.start, this_end=this_w.end,
            last_start=last_w.start, last_end=last_w.end,
        )

    return Insights(
        window_label=window_label,
        checks=len(receipts),
        top_by_profit=top_by_profit,
        hours=hour_stats,
        baristas=barista_stats,
        wow=wow,
    )
