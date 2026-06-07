"""ProfitCalculator — сердце продукта.

Превращает выручку и расходы в P&L:

    Выручка
      − Себестоимость (COGS)     = Валовая прибыль
      − Операционные расходы      = Чистая прибыль

Дополнительно проверяет качество данных и помечает то, что искажает прибыль
(незаполненный ФОТ, раздутое «Прочее» с зашитой в него закупкой и т.п.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Mapping

from backend.models import ExpenseCategory

ZERO = Decimal("0")
COGS_CATEGORIES = {ExpenseCategory.COGS}


def rub(value) -> str:
    """Формат денег по-русски: 1 234 567 ₽."""
    return f"{Decimal(value):,.0f}".replace(",", " ") + " ₽"


def _pct(part: Decimal, whole: Decimal) -> float:
    if not whole:
        return 0.0
    return float((part / whole * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


@dataclass
class ProfitReport:
    period: str
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    operating_expenses: Decimal
    net_profit: Decimal
    gross_margin_pct: float
    net_margin_pct: float
    expenses: Dict[ExpenseCategory, Decimal]
    warnings: List[str] = field(default_factory=list)

    @property
    def total_expenses(self) -> Decimal:
        return self.cogs + self.operating_expenses


class ProfitCalculator:
    # Доля выручки, выше которой «Прочее» подозрительно — вероятно содержит закупку товара.
    OTHER_REVENUE_ALERT = Decimal("0.20")

    def compute(
        self,
        period: str,
        revenue: Decimal,
        expenses: Mapping[ExpenseCategory, Decimal],
    ) -> ProfitReport:
        revenue = Decimal(revenue)
        expenses = {c: Decimal(a) for c, a in expenses.items() if a}

        cogs = sum((expenses.get(c, ZERO) for c in COGS_CATEGORIES), ZERO)
        operating = sum(
            (a for c, a in expenses.items() if c not in COGS_CATEGORIES), ZERO
        )

        gross_profit = revenue - cogs
        net_profit = gross_profit - operating

        report = ProfitReport(
            period=period,
            revenue=revenue,
            cogs=cogs,
            gross_profit=gross_profit,
            operating_expenses=operating,
            net_profit=net_profit,
            gross_margin_pct=_pct(gross_profit, revenue),
            net_margin_pct=_pct(net_profit, revenue),
            expenses=dict(expenses),
        )
        report.warnings = self._check_data_quality(report)
        return report

    def _check_data_quality(self, r: ProfitReport) -> List[str]:
        warns: List[str] = []
        if r.cogs == ZERO:
            warns.append(
                "COGS не задан: валовая прибыль = выручке. "
                "Маржу по товарам не посчитать без справочника себестоимости."
            )
        if r.expenses.get(ExpenseCategory.PAYROLL, ZERO) == ZERO:
            warns.append("ФОТ = 0 — данные не внесены, чистая прибыль завышена.")
        other = r.expenses.get(ExpenseCategory.OTHER, ZERO)
        if r.revenue and other > r.revenue * self.OTHER_REVENUE_ALERT:
            warns.append(
                f"«Прочее» = {rub(other)} ({_pct(other, r.revenue)}% выручки) — "
                "вероятно, сюда попала закупка товара (COGS)."
            )
        return warns
