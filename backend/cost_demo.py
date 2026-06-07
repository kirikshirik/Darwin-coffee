"""Демо: себестоимость напитков «Дарвина» и проверка гипотезы о «Прочее».

Чисто расчётный модуль (без БД). Запуск:
    .venv/bin/python -m backend.cost_demo

Что показывает:
  1. Раскладку себестоимости по объёмам 250 / 350 / 450 мл + сверку с Excel.
  2. Себестоимость допов (какао, матча, сироп, …).
  3. Проверку Находки 1: «Прочее» (~28% выручки) — это, вероятно, закупка товара.
     Зная себестоимость чашки, выводим, какой средний чек на напиток это
     подразумевает, и оцениваем, реалистичен ли он.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from backend import cost_reference as cr
from backend import darwin_data
from backend.financial.profit_calculator import rub
from backend.models import ExpenseCategory


def _r2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def kop(value) -> str:
    """Деньги с копейками: 16,92 ₽ (для копеечных сумм рецепта)."""
    s = f"{_r2(value):,.2f}".replace(",", " ").replace(".", ",")
    return s + " ₽"


def main() -> None:
    print("\n☕ Справочник себестоимости «Дарвина» (из расчёта фуд-коста)\n")

    # --- 1. Базовые позиции по объёму ---
    print("Базовая кофейная позиция (всё, кроме РАФ):")
    print(f"  {'Объём':<8}{'Себестоимость':>16}{'Сверка с Excel':>18}")
    print("  " + "-" * 40)
    checks = cr.verify_against_excel()
    for vol in sorted(cr.BASE_DRINKS):
        mark = "✅" if checks[vol] else "❌"
        print(
            f"  {str(vol) + ' мл':<8}{kop(cr.base_cost(vol)):>16}"
            f"{mark + ' ' + kop(cr.CONTROL[vol]):>20}"
        )
    all_ok = all(checks.values())
    print("  =>", "✅ ВСЕ ПОЗИЦИИ СОВПАДАЮТ с Excel" if all_ok else "❌ РАСХОЖДЕНИЕ")

    # Детализация самой ходовой позиции (250 мл).
    print("\n  Состав 250 мл:")
    for comp, amount in cr.BASE_DRINKS[250].items():
        print(f"    {comp:<14}{kop(amount):>12}")

    # --- 1b. Аудит заявленных закупочных цен (которого нет в Excel) ---
    print("\nАудит закупочных цен (заявленная цена × расход порции vs расчёт владельца):")
    print(f"  {'компонент':<10}{'расход':<9}{'по цене':>12}{'в расчёте':>13}{'δ':>12}")
    print("  " + "-" * 56)
    audit = cr.audit_input_prices()
    for r in audit:
        if r["ok"]:
            delta_str, mark = "0", "✅"
        else:
            sign = "+" if r["delta"] > 0 else "−"
            delta_str, mark = f"{sign}{kop(abs(r['delta']))}", "⚠️"
        print(
            f"  {r['name']:<10}{r['dose']:<9}{kop(r['expected']):>12}"
            f"{kop(r['documented']):>13}{delta_str:>12} {mark}"
        )
    bad = [r for r in audit if not r["ok"]]
    print(f"  => {len(audit) - len(bad)} из {len(audit)} заявленных цен сходятся с расчётом.")
    for r in bad:
        print(f"     • {r['name']}: {r['note']}")

    # --- 2. Допы ---
    print("\nДопы (прибавляются к базовой себестоимости):")
    for name, amount in cr.ADDONS.items():
        print(f"  {name:<18}{kop(amount):>12}")
    print(
        "  Без себестоимости порции (в Excel не заполнено): "
        + ", ".join(cr.ADDONS_NO_COST)
    )

    # Пример комбинации.
    latte_syrup = cr.drink_cost(350, "сироп")
    print(f"\n  Пример: латте 350 мл + сироп → {kop(latte_syrup)}")

    # --- 3. Проверка Находки 1: «Прочее» = закупка товара? ---
    other_total = sum(
        m["expenses"].get(ExpenseCategory.OTHER, Decimal("0"))
        for m in darwin_data.MONTHLY
    )
    revenue = darwin_data.EXCEL_ANNUAL["revenue"]
    other_share = _r2(other_total / revenue * 100)

    avg_cost = _r2(
        sum(cr.base_cost(v) for v in cr.BASE_DRINKS) / len(cr.BASE_DRINKS)
    )
    # Если «Прочее» — это COGS, то фуд-кост ≈ доле «Прочего» в выручке.
    # Тогда средний чек на напиток = себестоимость чашки / фуд-кост.
    implied_price = _r2(avg_cost / (other_share / 100))

    print("\nПроверка Находки 1 — «Прочее» это закупка товара (COGS)?")
    print(f"  «Прочее» за 12 мес:        {rub(other_total)} ({other_share}% выручки)")
    print(f"  Средняя себестоимость чашки: {kop(avg_cost)} (из справочника рецептов)")
    print(
        f"  Если «Прочее» = закупка, то фуд-кост ≈ {other_share}%, "
        f"а значит средний чек на напиток ≈ {kop(implied_price)}."
    )
    realistic = Decimal("180") <= implied_price <= Decimal("400")
    verdict = (
        "реалистичный чек для спеца → гипотеза «Прочее = COGS» подтверждается ✅"
        if realistic
        else "чек вне типичного диапазона → гипотезу нужно перепроверить ⚠️"
    )
    print(f"  Вывод: {verdict}")
    print(
        "\n  Теперь, имея справочник, маржу по товарам можно считать честно: "
        "цена продажи − себестоимость из рецепта."
    )


if __name__ == "__main__":
    main()
