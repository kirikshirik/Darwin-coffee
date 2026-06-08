"""Моделирование «что если» и точка безубыточности (break-even).

Владелец вводит параметры — «аренда выросла на 15%, трафик упал на 10%» — и видит
новый P&L и когда наступает безубыточность. Вся арифметика — через существующий
`ProfitCalculator` (бот ничего не считает сам), поэтому сценарий = базовый расчёт
с применёнными сдвигами + сравнение.

Модель сдвигов (прозрачная и защитимая):
  • трафик (объём)  → масштабирует выручку И переменную себестоимость (COGS);
  • цена            → масштабирует только выручку (COGS не зависит от цены продажи);
  • операционные    → множители/добавки по статьям (аренда ×1.15 и т.п.);
  • COGS-множитель  → удорожание сырья у поставщика поверх объёма (молоко +10%).

Точка безубыточности — через маржинальный доход:
  Постоянные расходы = операционные (всё, кроме COGS).
  Маржинальный доход = Выручка − COGS.
  Безубыточная выручка = Постоянные / (Маржинальный доход / Выручка).
  Безубыточный трафик  = Постоянные / Маржинальный доход (доля текущего объёма).

Деньги — только Decimal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal as D, ROUND_HALF_UP
from typing import Dict, Mapping, Optional

from backend.models import ExpenseCategory
from backend.financial.profit_calculator import (
    ProfitCalculator,
    ProfitReport,
    COGS_CATEGORIES,
)

ZERO = D("0")
ONE = D("1")


def _r2(x: D) -> D:
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _pct(part: D, whole: D) -> float:
    if not whole:
        return 0.0
    return float((part / whole * 100).quantize(D("0.1"), rounding=ROUND_HALF_UP))


@dataclass
class Scenario:
    """Набор сдвигов к базовому P&L.

    Множители заданы как доля: трафик −10% → traffic_factor = 0.90; аренда +15% →
    expense_factors = {RENT: 1.15}. `cogs_factor` — удорожание сырья поверх объёма.
    """

    name: str = "Сценарий"
    traffic_factor: D = ONE
    price_factor: D = ONE
    cogs_factor: D = ONE
    expense_factors: Dict[ExpenseCategory, D] = field(default_factory=dict)
    expense_deltas: Dict[ExpenseCategory, D] = field(default_factory=dict)

    @classmethod
    def from_pct(
        cls,
        name: str = "Сценарий",
        traffic_pct: D = ZERO,
        price_pct: D = ZERO,
        cogs_pct: D = ZERO,
        expense_pct: Optional[Dict[ExpenseCategory, D]] = None,
        expense_add: Optional[Dict[ExpenseCategory, D]] = None,
    ) -> "Scenario":
        """Удобный конструктор из процентов: traffic_pct=-10 → трафик −10%."""
        def f(pct) -> D:
            return (D("100") + D(pct)) / D("100")
        return cls(
            name=name,
            traffic_factor=f(traffic_pct),
            price_factor=f(price_pct),
            cogs_factor=f(cogs_pct),
            expense_factors={c: f(p) for c, p in (expense_pct or {}).items()},
            expense_deltas={c: D(v) for c, v in (expense_add or {}).items()},
        )

    def transform(
        self, revenue: D, expenses: Mapping[ExpenseCategory, D]
    ) -> tuple[D, Dict[ExpenseCategory, D]]:
        """Применяет сдвиги к выручке и статьям расходов."""
        new_revenue = D(revenue) * self.traffic_factor * self.price_factor
        new_expenses: Dict[ExpenseCategory, D] = {}
        for cat, amount in expenses.items():
            amount = D(amount)
            if cat in COGS_CATEGORIES:
                # переменная: растёт с объёмом (трафик) и с ценой сырья (cogs_factor)
                amount = amount * self.traffic_factor * self.cogs_factor
            else:
                amount = amount * self.expense_factors.get(cat, ONE)
                amount = amount + self.expense_deltas.get(cat, ZERO)
            new_expenses[cat] = amount
        # статья, которой не было в базе, но её добавил сценарий (например, MARKETING)
        for cat, delta in self.expense_deltas.items():
            if cat not in new_expenses:
                new_expenses[cat] = D(delta)
        return new_revenue, new_expenses


@dataclass
class BreakEven:
    """Точка безубыточности относительно набора (выручка, расходы)."""

    fixed_costs: D           # постоянные = операционные (без COGS)
    contribution: D          # маржинальный доход = выручка − COGS
    contribution_margin_pct: float
    break_even_revenue: D    # выручка, при которой чистая прибыль = 0
    break_even_traffic_pct: float   # на сколько % может упасть трафик до нуля прибыли
    feasible: bool           # достижима ли вообще (маржинальный доход > 0)
    note: str = ""


def break_even(revenue: D, expenses: Mapping[ExpenseCategory, D]) -> BreakEven:
    """Считает точку безубыточности маржинальным методом."""
    revenue = D(revenue)
    cogs = sum((D(expenses.get(c, ZERO)) for c in COGS_CATEGORIES), ZERO)
    fixed = sum((D(a) for c, a in expenses.items() if c not in COGS_CATEGORIES), ZERO)
    contribution = revenue - cogs
    cm_pct = _pct(contribution, revenue)

    if contribution <= ZERO:
        return BreakEven(
            fixed_costs=_r2(fixed), contribution=_r2(contribution),
            contribution_margin_pct=cm_pct, break_even_revenue=ZERO,
            break_even_traffic_pct=0.0, feasible=False,
            note="Маржинальный доход ≤ 0: безубыточность недостижима без роста цены/маржи.",
        )

    cm_ratio = contribution / revenue
    be_revenue = fixed / cm_ratio
    # безубыточный трафик: доля текущего объёма, при которой прибыль = 0
    be_traffic_factor = fixed / contribution
    # на сколько % можно просесть по трафику (отрицательное значение = запас прочности)
    drop_pct = float(((be_traffic_factor - ONE) * 100).quantize(D("0.1"), rounding=ROUND_HALF_UP))
    return BreakEven(
        fixed_costs=_r2(fixed),
        contribution=_r2(contribution),
        contribution_margin_pct=cm_pct,
        break_even_revenue=_r2(be_revenue),
        break_even_traffic_pct=drop_pct,
        feasible=True,
    )


@dataclass
class ScenarioResult:
    scenario: Scenario
    baseline: ProfitReport
    projected: ProfitReport
    baseline_break_even: BreakEven
    projected_break_even: BreakEven

    @property
    def revenue_delta(self) -> D:
        return _r2(self.projected.revenue - self.baseline.revenue)

    @property
    def net_profit_delta(self) -> D:
        return _r2(self.projected.net_profit - self.baseline.net_profit)

    @property
    def net_margin_delta(self) -> float:
        return round(self.projected.net_margin_pct - self.baseline.net_margin_pct, 1)

    @property
    def turned_unprofitable(self) -> bool:
        return self.baseline.net_profit > ZERO >= self.projected.net_profit


def apply(
    period: str,
    revenue: D,
    expenses: Mapping[ExpenseCategory, D],
    scenario: Scenario,
    calculator: Optional[ProfitCalculator] = None,
) -> ScenarioResult:
    """Считает базовый и сценарный P&L через ProfitCalculator + точки безубыточности."""
    calc = calculator or ProfitCalculator()
    baseline = calc.compute(period, revenue, expenses)
    new_revenue, new_expenses = scenario.transform(revenue, expenses)
    projected = calc.compute(f"{period} · {scenario.name}", new_revenue, new_expenses)
    return ScenarioResult(
        scenario=scenario,
        baseline=baseline,
        projected=projected,
        baseline_break_even=break_even(revenue, expenses),
        projected_break_even=break_even(new_revenue, new_expenses),
    )
