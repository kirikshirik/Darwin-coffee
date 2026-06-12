"""Метрики для бота — вся арифметика через ProfitCalculator (без дублирования формул).

Два источника данных, ровно по архитектуре проекта:
  • Чеки из Эвотора (таблицы receipts/receipt_items) → дневные/недельные отчёты.
    Пока Cloud Token не подключён, чеков нет → отчёты честно говорят «нет данных».
  • Помесячный честный P&L из Excel-данных (`darwin_data` + overlay `actuals_data`) →
    отчёт «Месяц». Работает уже сейчас — это и есть headline-ценность продукта.

Операционные расходы — помесячные; для дневных/недельных отчётов раскидываем их по
дням пропорционально (monthly / дней_в_месяце). COGS для чековых отчётов берётся из
реальной себестоимости позиций (receipt_items.cost), а не из прокси «Прочее».

Модуль чистый: НЕ импортирует aiogram, поэтому проверяется offline (см. bot/demo.py).
Деньги — только Decimal.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend import actuals_data, darwin_data
from backend.financial.profit_calculator import ProfitCalculator, ProfitReport
from backend.models import Business, ExpenseCategory as C, Receipt, ReceiptItem

ZERO = Decimal("0")
CENT = Decimal("0.01")
_CALC = ProfitCalculator()


@dataclass
class TopProduct:
    name: str
    qty: Decimal
    revenue: Decimal
    profit: Decimal


@dataclass
class PeriodReport:
    """Готовый отчёт за период: P&L + сводка по чекам + источник данных."""

    label: str
    start: date
    end: date
    report: ProfitReport
    checks_count: int = 0
    avg_check: Decimal = ZERO
    top_products: List[TopProduct] = field(default_factory=list)
    from_receipts: bool = False          # данные из чеков Эвотора (vs помесячный Excel)
    cogs_is_proxy: bool = False          # COGS оценён по «Прочее» (нет реального food cost)
    source: str = ""

    @property
    def has_data(self) -> bool:
        # Для чековых отчётов «есть данные» = есть чеки; для помесячных — всегда есть.
        return self.checks_count > 0 if self.from_receipts else self.report.revenue > 0


# --- бизнес и периоды -------------------------------------------------------------
def get_business_id(session: Session) -> int:
    biz = session.scalars(select(Business).order_by(Business.id)).first()
    if biz is None:
        raise RuntimeError("В БД нет бизнеса. Сначала: .venv/bin/python -m backend.seed")
    return biz.id


def _find_month(period: date) -> Optional[dict]:
    key = date(period.year, period.month, 1)
    for m in darwin_data.MONTHLY:
        if m["period"] == key:
            return m
    return None


def latest_month_period() -> date:
    return max(m["period"] for m in darwin_data.MONTHLY)


# --- честный помесячный разбор (единый источник для месяца и для проразбивки) ------
def honest_month(period: date) -> Optional[dict]:
    """Честный разбор месяца: COGS + операционка (с реальным ФОТ).

    ЗЕРКАЛИТ логику `backend.honest_report` (там она печатается, тут — переиспользуема
    ботом). Держать в синхроне; bot/demo.py сверяет годовой итог с honest_report.

    Возвращает {revenue, cogs, cogs_is_proxy, operating: {category: amount, …}}.
    operating ВКЛЮЧАЕТ ФОТ (реальный — из дневного отчёта/владельца, где есть).

    COGS по приоритету: реальный food cost (дневной отчёт) → средний реальный
    (для месяца с ФОТ-фактом, но без food cost — сейчас сентябрь) → прокси «Прочее».
    """
    m = _find_month(period)
    if m is None:
        return None
    rev, exp = m["revenue"], m["expenses"]
    period_key = date(period.year, period.month, 1)
    act = actuals_data.ACTUALS.get(period_key)

    # операционка = все статьи Excel, кроме «Прочего» (оно = COGS) и ФОТ (ставим явно)
    operating: Dict[C, Decimal] = {
        cat: amt for cat, amt in exp.items() if cat not in (C.OTHER, C.PAYROLL)
    }

    if act:
        # реальный food cost, но если месяц закрыт с неполными закупками — реалистичная оценка
        cogs, cogs_is_proxy = actuals_data.effective_food_cost(rev, act["food_cost"])
        payroll = act["payroll"]
    else:
        extra = actuals_data.PAYROLL_EXTRA.get(period_key)
        if extra is not None:
            # ФОТ — факт от владельца, food cost неизвестен → средний реальный (окт–май)
            cogs, cogs_is_proxy = actuals_data.avg_food_cost(), True
            payroll = extra
        else:
            cogs, cogs_is_proxy = exp.get(C.OTHER, ZERO), True  # прокси: «Прочее» ≈ закупка
            payroll = exp.get(C.PAYROLL)

    if payroll:
        operating[C.PAYROLL] = payroll

    return {"revenue": rev, "cogs": cogs, "cogs_is_proxy": cogs_is_proxy, "operating": operating}


def monthly_report(period: Optional[date] = None) -> PeriodReport:
    """Честный P&L за месяц из Excel-данных (работает без Эвотора). По умолчанию — последний месяц."""
    period = period or latest_month_period()
    hm = honest_month(period)
    if hm is None:
        raise ValueError(f"Нет помесячных данных за {period:%Y-%m}")

    expenses = {C.COGS: hm["cogs"], **hm["operating"]}
    report = _CALC.compute(_month_label(period), hm["revenue"], expenses)
    last_day = date(period.year, period.month, monthrange(period.year, period.month)[1])
    source = "Excel помесячно · честный P&L"
    if hm["cogs_is_proxy"]:
        source += " · COGS=оценка по «Прочее»"
    return PeriodReport(
        label=_month_label(period),
        start=date(period.year, period.month, 1),
        end=last_day,
        report=report,
        from_receipts=False,
        cogs_is_proxy=hm["cogs_is_proxy"],
        source=source,
    )


# --- чековые отчёты (из Эвотора) --------------------------------------------------
def _operating_for_range(start: date, end: date) -> Dict[C, Decimal]:
    """Помесячная операционка, раскиданная по дням периода [start, end] включительно.

    Для текущего/будущего месяца, которого ещё нет в Excel-P&L (`darwin_data`),
    берём операционку последнего известного месяца — фикс. расходы (аренда, ФОТ,
    налоги) стабильны. Иначе чековые отчёты живого месяца показывали бы opex=0 и
    завышенную «чистую прибыль». Тот же приём, что в forecast._operating_estimate.
    """
    acc: Dict[C, Decimal] = defaultdict(lambda: ZERO)
    d = start
    while d <= end:
        hm = honest_month(date(d.year, d.month, 1)) or honest_month(latest_month_period())
        if hm:
            dim = monthrange(d.year, d.month)[1]
            for cat, amt in hm["operating"].items():
                acc[cat] += amt / dim
        d += timedelta(days=1)
    return {cat: v.quantize(CENT, rounding=ROUND_HALF_UP) for cat, v in acc.items()}


def sales_aggregate(session: Session, business_id: int, start_dt: datetime, end_dt: datetime):
    """Свод по чекам в [start_dt, end_dt): выручка, реальный COGS, чеки, топ товаров."""
    receipts = session.scalars(
        select(Receipt)
        .options(selectinload(Receipt.items).selectinload(ReceiptItem.product))
        .where(
            Receipt.business_id == business_id,
            Receipt.sold_at >= start_dt,
            Receipt.sold_at < end_dt,
        )
    ).all()

    revenue = sum((r.total_sum for r in receipts), ZERO)
    cogs = ZERO
    agg: Dict[str, List[Decimal]] = {}  # name -> [qty, revenue, profit]
    for r in receipts:
        for it in r.items:
            cogs += it.cost
            name = it.product.name if it.product else "(прочее)"
            cell = agg.setdefault(name, [ZERO, ZERO, ZERO])
            cell[0] += it.quantity
            cell[1] += it.revenue
            cell[2] += it.profit

    top = sorted(
        (TopProduct(n, v[0], v[1], v[2]) for n, v in agg.items()),
        key=lambda t: t.profit,
        reverse=True,
    )
    return {"revenue": revenue, "cogs": cogs, "checks": len(receipts), "top": top}


def report_for_range(
    session: Session,
    business_id: int,
    start_dt: datetime,
    end_dt: datetime,
    label: str,
) -> PeriodReport:
    """Отчёт по чекам Эвотора за [start_dt, end_dt). Если чеков нет — has_data=False."""
    agg = sales_aggregate(session, business_id, start_dt, end_dt)
    expenses = {C.COGS: agg["cogs"]}
    last_day = (end_dt - timedelta(seconds=1)).date()
    expenses.update(_operating_for_range(start_dt.date(), last_day))

    report = _CALC.compute(label, agg["revenue"], expenses)
    avg = (agg["revenue"] / agg["checks"]).quantize(CENT, rounding=ROUND_HALF_UP) if agg["checks"] else ZERO
    return PeriodReport(
        label=label,
        start=start_dt.date(),
        end=last_day,
        report=report,
        checks_count=agg["checks"],
        avg_check=avg,
        top_products=agg["top"][:5],
        from_receipts=True,
        source="Эвотор · чеки",
    )


def day_report(session: Session, business_id: int, day: date, label: Optional[str] = None) -> PeriodReport:
    start = datetime(day.year, day.month, day.day)
    return report_for_range(session, business_id, start, start + timedelta(days=1), label or _day_label(day))


def week_report(session: Session, business_id: int, end_day: date) -> PeriodReport:
    start_day = end_day - timedelta(days=6)
    start = datetime(start_day.year, start_day.month, start_day.day)
    end = datetime(end_day.year, end_day.month, end_day.day) + timedelta(days=1)
    return report_for_range(session, business_id, start, end, f"Неделя {start_day:%d.%m}–{end_day:%d.%m}")


def month_to_date_report(session: Session, business_id: int, today: date) -> PeriodReport:
    """Текущий месяц по чекам (с 1-го числа). Для «Месяц», когда есть данные Эвотора."""
    start = datetime(today.year, today.month, 1)
    end = datetime(today.year, today.month, today.day) + timedelta(days=1)
    return report_for_range(session, business_id, start, end, f"{_month_label(today)} (по {today:%d.%m})")


# --- расходы (для кнопки «Расходы») -----------------------------------------------
def expenses_breakdown(period: Optional[date] = None):
    """Разбивка расходов за месяц: список (категория, сумма) + итог. Честный (COGS+ФОТ)."""
    period = period or latest_month_period()
    hm = honest_month(period)
    if hm is None:
        raise ValueError(f"Нет данных за {period:%Y-%m}")
    rows: List[tuple] = [(C.COGS.value, hm["cogs"])]
    for cat, amt in sorted(hm["operating"].items(), key=lambda kv: kv[1], reverse=True):
        rows.append((cat.value, amt))
    total = sum((amt for _, amt in rows), ZERO)
    return period, rows, total


# --- подписи периодов -------------------------------------------------------------
_RU_MONTHS = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь",
    7: "июль", 8: "август", 9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
}


def _month_label(d: date) -> str:
    return f"{_RU_MONTHS[d.month].capitalize()} {d.year}"


def _day_label(d: date) -> str:
    return d.strftime("%d.%m.%Y")
