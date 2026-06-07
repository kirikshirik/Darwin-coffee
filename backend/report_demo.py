"""Демо: считает P&L «Дарвина» из БД и сверяет с Excel.

Запуск:
    .venv/bin/python -m backend.seed         # сначала наполнить БД
    .venv/bin/python -m backend.report_demo  # затем отчёт
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select

from backend import darwin_data
from backend.db import SessionLocal
from backend.financial.profit_calculator import ProfitCalculator, rub
from backend.models import Business, Expense, ExpenseCategory

RU_MONTHS = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}


def month_label(d) -> str:
    return f"{RU_MONTHS[d.month]} {str(d.year)[2:]}"


def main() -> None:
    calc = ProfitCalculator()
    revenue_by_period = {m["period"]: m["revenue"] for m in darwin_data.MONTHLY}

    with SessionLocal() as session:
        biz = session.scalars(select(Business)).first()
        if biz is None:
            raise SystemExit("Нет данных. Сначала: .venv/bin/python -m backend.seed")

        exp_by_period = defaultdict(dict)
        for e in session.scalars(select(Expense).where(Expense.business_id == biz.id)):
            exp_by_period[e.period][e.category] = e.amount

    print(f"\n☕ {biz.name} — P&L за 12 месяцев (рассчитан из БД)\n")
    print(f"{'Месяц':<8}{'Выручка':>13}{'Расходы':>13}{'Чистая приб.':>15}{'Маржа':>8}  Флаг")
    print("-" * 64)

    reports = []
    tot_rev = tot_exp = tot_net = Decimal("0")
    for period in sorted(exp_by_period):
        rev = revenue_by_period.get(period, Decimal("0"))
        r = calc.compute(month_label(period), rev, exp_by_period[period])
        reports.append(r)
        tot_rev += r.revenue
        tot_exp += r.total_expenses
        tot_net += r.net_profit
        flag = "⚠️ нет ФОТ" if any("ФОТ" in w for w in r.warnings) else ""
        print(
            f"{r.period:<8}{rub(r.revenue):>15}{rub(r.total_expenses):>15}"
            f"{rub(r.net_profit):>17}{r.net_margin_pct:>7}%  {flag}"
        )

    print("-" * 64)
    net_margin = float(tot_net / tot_rev * 100) if tot_rev else 0.0
    print(
        f"{'ИТОГО':<8}{rub(tot_rev):>15}{rub(tot_exp):>15}"
        f"{rub(tot_net):>17}{net_margin:>6.1f}%"
    )

    # --- контроль против Excel ---
    excel = darwin_data.EXCEL_ANNUAL
    ok = tot_rev == excel["revenue"] and tot_net == excel["net_profit"]
    print("\nКонтроль против Excel (строка «Сумма за период 12 мес»):")
    print(f"  Выручка:        расчёт {rub(tot_rev)}  | Excel {rub(excel['revenue'])}")
    print(f"  Чистая прибыль: расчёт {rub(tot_net)}  | Excel {rub(excel['net_profit'])}")
    print("  =>", "✅ СОВПАДАЕТ" if ok else "❌ РАСХОЖДЕНИЕ")

    # --- влияние пропусков в данных ---
    no_payroll = [r for r in reports if any("ФОТ" in w for w in r.warnings)]
    payrolls = [
        r.expenses[ExpenseCategory.PAYROLL]
        for r in reports
        if ExpenseCategory.PAYROLL in r.expenses
    ]
    print("\nКачество данных:")
    print(
        f"  Месяцев без ФОТ: {len(no_payroll)} из {len(reports)} "
        f"({', '.join(r.period for r in no_payroll)})"
    )
    if payrolls and no_payroll:
        avg_payroll = sum(payrolls) / len(payrolls)
        hidden = avg_payroll * len(no_payroll)
        print(f"  Средний ФОТ (где внесён): {rub(avg_payroll)}")
        print(
            f"  Недоучтённый ФОТ ≈ {rub(hidden)}  →  "
            f"реальная годовая прибыль ≈ {rub(tot_net - hidden)} "
            f"(в Excel показано {rub(tot_net)})"
        )


if __name__ == "__main__":
    main()
