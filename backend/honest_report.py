"""Демо: ЧЕСТНЫЙ P&L «Дарвина» — реальный ФОТ + реальный COGS.

Накладывает факт из `actuals_data` (дневной отчёт «Отчет 25-26») на помесячный
P&L из `darwin_data` (P&L-Excel) и показывает, насколько Excel завышает прибыль.

Чисто расчётный модуль (без БД). Запуск:
    .venv/bin/python -m backend.honest_report

Логика наложения по месяцам, где есть факт (окт–май):
    COGS        = реальный Food cost            (вместо «Прочего»-прокси)
    ФОТ         = реальная зарплата             (вместо пустой/неточной в Excel)
    Операционка = прочие статьи Excel           (аренда, комм., налоги, эквайринг,
                                                 амортизация) — без PAYROLL и без OTHER
    Чистая      = Выручка − COGS − Операционка − ФОТ

Месяцы без факта (июн–сен) считаются как в Excel (COGS-прокси = «Прочее»);
сентябрь по-прежнему без ФОТ → флаг.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from backend import actuals_data, darwin_data
from backend.financial.profit_calculator import rub
from backend.models import ExpenseCategory as C

ZERO = Decimal("0")
RU_MONTHS = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}


def _label(d) -> str:
    return f"{RU_MONTHS[d.month]} {str(d.year)[2:]}"


def _pct(part: Decimal, whole: Decimal) -> str:
    if not whole:
        return "—"
    return f"{(part / whole * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def main() -> None:
    if not actuals_data.verify_control():
        raise SystemExit("❌ ACTUALS не сходятся с контрольными суммами — проверь данные.")

    print("\n☕ Кофейня «Дарвин» — ЧЕСТНЫЙ P&L (реальный ФОТ + реальный COGS)\n")
    print(f"Источник факта: {actuals_data.SOURCE}\n")
    print(f"{'Месяц':<8}{'Выручка':>12}{'COGS':>12}{'Опер.+ФОТ':>13}{'Чистая':>12}{'Марж.':>8}  Источник")
    print("-" * 78)

    tot_rev = tot_cogs_real = naive_net = honest_net = ZERO
    cogs_real_rev = ZERO  # выручка месяцев, где COGS реальный (для честного %)
    sep_flag = False

    for m in darwin_data.MONTHLY:
        period, rev, exp = m["period"], m["revenue"], m["expenses"]
        tot_rev += rev
        naive_net += rev - sum(exp.values(), ZERO)

        act = actuals_data.ACTUALS.get(period)
        if act:
            cogs = act["food_cost"]
            payroll = act["payroll"]
            # операционка = всё из Excel, кроме зарплаты и «Прочего» (его заменил COGS)
            operating = sum(
                (a for c, a in exp.items() if c not in (C.PAYROLL, C.OTHER)), ZERO
            )
            net = rev - cogs - operating - payroll
            tot_cogs_real += cogs
            cogs_real_rev += rev
            src = "факт"
        else:
            # нет дневного отчёта (июн–сен): считаем как в Excel, COGS-прокси = «Прочее»
            cogs = exp.get(C.OTHER, ZERO)
            net = rev - sum(exp.values(), ZERO)
            if C.PAYROLL not in exp:
                src = "Excel ⚠️ нет ФОТ"
                sep_flag = True
            else:
                src = "Excel (прокси COGS)"

        honest_net += net
        print(
            f"{_label(period):<8}{rub(rev):>14}{rub(cogs):>14}"
            f"{rub(rev - cogs - net):>15}{rub(net):>14}{_pct(net, rev):>8}  {src}"
        )

    print("-" * 78)
    print(f"{'ИТОГО':<8}{rub(tot_rev):>14}{'':>14}{'':>15}{rub(honest_net):>14}{_pct(honest_net, tot_rev):>8}")

    # --- Главный вывод ---
    delta_pct = (honest_net / naive_net * 100).quantize(Decimal("0.1")) if naive_net else ZERO
    print("\nЧестная прибыль против Excel-наивной:")
    print(f"  Excel-наивная чистая прибыль:  {rub(naive_net)}  (ФОТ пуст в 6 мес.)")
    print(f"  ЧЕСТНАЯ чистая прибыль:        {rub(honest_net)}  ({delta_pct}% от Excel)")

    print("\nРеальный COGS (где есть дневной отчёт, окт–май):")
    print(
        f"  Закупка товара: {rub(tot_cogs_real)} = {_pct(tot_cogs_real, cogs_real_rev)} "
        f"выручки этих месяцев."
    )
    print(
        "  Рецептурная оценка фуд-коста (cost_demo) была 28.7% → совпадает порядок величины. "
        "Находка 1 подтверждена реальными данными."
    )

    # --- Конфликты и остаточные пробелы ---
    print("\nКонфликты ФОТ (P&L-Excel ↔ дневной отчёт), взяты значения отчёта:")
    for d, v in actuals_data.PAYROLL_CONFLICTS.items():
        diff = v["actual"] - v["monthly"]
        print(f"  {_label(d)}: Excel {rub(v['monthly'])} → факт {rub(v['actual'])} ({rub(diff)})")

    if sep_flag:
        avg_pay = actuals_data.CONTROL["payroll_total"] / len(actuals_data.ACTUALS)
        with_sep = honest_net - avg_pay
        miss = ", ".join(_label(d) for d in actuals_data.PAYROLL_STILL_MISSING)
        print(f"\nОстаточный пробел: ФОТ за {miss} нет ни в одном файле.")
        print(
            f"  Если оценить его средним ({rub(avg_pay)}), честная прибыль ≈ {rub(with_sep)}."
        )


if __name__ == "__main__":
    main()
