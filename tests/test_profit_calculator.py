"""Контрольные тесты ядра: те же сверки, что demo-скрипты, но в pytest.

Эти суммы — суть продукта: 899 565 ₽ — копия Excel владельца (наивный P&L),
334 651 ₽ — честная прибыль с реальным ФОТ и COGS. Любое расхождение означает,
что сломан калькулятор, данные или overlay факта.
"""
from decimal import Decimal

from backend import darwin_data
from backend.bot import metrics
from backend.financial.profit_calculator import ProfitCalculator
from backend.models import ExpenseCategory as C

ZERO = Decimal("0")


def test_excel_annual_control():
    """P&L из MONTHLY копейка-в-копейку сходится с Excel (как report_demo)."""
    calc = ProfitCalculator()
    tot_rev = tot_net = ZERO
    for m in darwin_data.MONTHLY:
        r = calc.compute("t", m["revenue"], m["expenses"])
        tot_rev += r.revenue
        tot_net += r.net_profit
    assert tot_rev == darwin_data.EXCEL_ANNUAL["revenue"] == Decimal("3733684")
    assert tot_net == darwin_data.EXCEL_ANNUAL["net_profit"] == Decimal("899565")


def test_honest_annual_control():
    """Честный P&L (факт поверх Excel) = 334 651 ₽/год (как bot.demo/honest_report)."""
    total = ZERO
    for m in darwin_data.MONTHLY:
        hm = metrics.honest_month(m["period"])
        total += hm["revenue"] - hm["cogs"] - sum(hm["operating"].values(), ZERO)
    assert total == Decimal("334651")


def test_missing_payroll_is_warning_not_zero():
    """Пустая ячейка ≠ 0: незаполненный ФОТ — флаг качества данных, а не расход 0 ₽."""
    calc = ProfitCalculator()
    r = calc.compute("t", Decimal("100000"), {C.RENT: Decimal("30000")})
    assert C.PAYROLL not in r.expenses
    assert any("ФОТ" in w for w in r.warnings)

    with_payroll = calc.compute("t", Decimal("100000"), {C.PAYROLL: Decimal("50000")})
    assert not any("ФОТ" in w for w in with_payroll.warnings)


def test_inflated_other_is_flagged():
    """«Прочее» больше 20% выручки — подозрение на спрятанную закупку (Находка 1)."""
    calc = ProfitCalculator()
    r = calc.compute("t", Decimal("100000"), {C.OTHER: Decimal("28000")})
    assert any("Прочее" in w for w in r.warnings)


def test_money_stays_decimal():
    calc = ProfitCalculator()
    r = calc.compute("t", Decimal("100"), {C.COGS: Decimal("30")})
    assert isinstance(r.net_profit, Decimal) and r.net_profit == Decimal("70")
