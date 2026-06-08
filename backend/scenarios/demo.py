"""Демо: LTV/средний чек и моделирование «что если» (без БД).

Запуск:
    .venv/bin/python -m backend.scenarios.demo

Что показывает:
  1. Меню из реальных тех-карт (себестоимость) + иллюстративные цены продажи →
     средний чек и маржа. Эффект ввода допа-сиропа (апсейл) на чек и маржу. LTV.
  2. Сценарий «аренда +15%, трафик −10%» поверх майского P&L → новый P&L,
     дельты прибыли/маржи и точка безубыточности (до и после сценария).

Цены продажи — иллюстративные (Эвотор их не отдаёт, нужны от владельца): модуль
честно помечает это предупреждениями. Себестоимость напитков — настоящая, из тех-карт.
"""
from __future__ import annotations

from decimal import Decimal as D, ROUND_HALF_UP

from backend.costing import techcard as tc
from backend.scenarios import menu as mn
from backend.scenarios import whatif as wi
from backend.scenarios.menu import MenuItem, MenuLine, Menu
from backend.models import ExpenseCategory as C
from backend.financial.profit_calculator import rub


def kop(value) -> str:
    s = f"{D(value).quantize(D('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return s.replace(",", " ").replace(".", ",") + " ₽"


def _pp(delta) -> str:
    return ("+" if delta >= 0 else "") + f"{delta:.1f} п.п."


def main() -> None:
    print("\n📈 Калькулятор LTV / среднего чека (тех-карты + цены продажи владельца)\n")

    # --- 1. Меню: себестоимость из тех-карт, цены продажи — иллюстративные ---
    # TODO(owner): заменить sell_price на реальные цены меню «Дарвина».
    cappuccino = MenuItem("Капучино 250", sell_price=D("200"), cost=tc.base_card(250).cost(), category="кофе")
    latte = MenuItem("Латте 350", sell_price=D("250"), cost=tc.base_card(350).cost(), category="кофе")
    pastry = MenuItem("Чизкейк", sell_price=D("220"), cost=D("90"), category="выпечка")  # cost — оценка владельца

    menu = Menu([
        MenuLine(cappuccino, D("600")),
        MenuLine(latte, D("400")),
        MenuLine(pastry, D("150")),
    ])
    m = menu.metrics()
    print("Меню за период (продажи):")
    for line in menu.lines:
        it = line.item
        print(f"  {it.name:<16}цена {kop(it.sell_price):>10}  себест. {kop(it.cost):>9}  "
              f"маржа {it.margin_pct:>5.1f}%   ×{int(line.units)}")
    print("  " + "-" * 58)
    print(f"  Выручка {rub(m.revenue)} · средняя цена позиции {kop(m.avg_item_price)} · "
          f"маржа {m.margin_pct:.1f}%")
    for w in m.warnings:
        print(f"  ⚠️ {w}")

    checks_count = 700  # пример: 700 чеков за период
    # Эффект допа-сиропа: берут к 30% проданных позиций, +50 ₽ к чеку, себест. 6 ₽.
    syrup = MenuItem("Сироп (доп)", sell_price=D("50"), cost=D("6"), category="доп")
    impact = mn.impact_of_addon(menu, syrup, attach_rate=D("0.30"), checks_count=D(checks_count))
    print("\nЧто если ввести сироп-апсейл (берут к 30% позиций, +50 ₽):")
    print(f"  Средний чек:          {kop(impact.avg_check_before)} → "
          f"{kop(impact.avg_check_after)} ({'+' if impact.avg_check_delta>=0 else ''}{kop(impact.avg_check_delta)})")
    print(f"  Маржа меню:           {impact.margin_pct_before:.1f}% → "
          f"{impact.margin_pct_after:.1f}% ({_pp(impact.margin_pct_delta)})")
    print(f"  Прибыль за период:    {rub(impact.profit_before)} → {rub(impact.profit_after)} "
          f"(+{rub(impact.profit_delta)})")

    # LTV (с явными допущениями)
    avg_check = menu.avg_check(checks_count=checks_count)
    lt = mn.ltv(avg_check=avg_check, visits_per_month=D("6"),
                lifespan_months=D("12"), margin_pct=m.margin_pct)
    print(f"\nLTV: чек {kop(lt.avg_check)} × 6 визитов/мес × 12 мес × маржа {lt.margin_pct:.1f}% "
          f"= {rub(lt.value)}")
    for w in lt.warnings:
        print(f"  ⚠️ {w}")

    # --- 2. Моделирование «что если» + break-even ---
    print("\n\n🔮 Моделирование «что если» (поверх майского P&L)\n")
    revenue = D("306497")
    expenses = {
        C.COGS: D("25000"), C.RENT: D("84530"), C.UTILITIES: D("9135"),
        C.PAYROLL: D("80400"), C.TAXES: D("5977"),
    }
    scenario = wi.Scenario.from_pct(
        "Аренда +15%, трафик −10%",
        traffic_pct=D("-10"),
        expense_pct={C.RENT: D("15")},
    )
    res = wi.apply("Май 2026", revenue, expenses, scenario)

    b, p = res.baseline, res.projected
    print(f"  {'Показатель':<22}{'База':>14}{'Сценарий':>16}{'Δ':>14}")
    print("  " + "-" * 66)
    print(f"  {'Выручка':<22}{rub(b.revenue):>14}{rub(p.revenue):>16}{rub(res.revenue_delta):>14}")
    print(f"  {'Чистая прибыль':<22}{rub(b.net_profit):>14}{rub(p.net_profit):>16}{rub(res.net_profit_delta):>14}")
    print(f"  {'Чистая маржа':<22}{str(b.net_margin_pct)+'%':>14}{str(p.net_margin_pct)+'%':>16}{_pp(res.net_margin_delta):>14}")

    be_b, be_p = res.baseline_break_even, res.projected_break_even
    print("\n  Точка безубыточности:")
    print(f"    База:     выручка {rub(be_b.break_even_revenue)} "
          f"(запас по трафику {-be_b.break_even_traffic_pct:.1f}%, маржин. доход {be_b.contribution_margin_pct}%)")
    print(f"    Сценарий: выручка {rub(be_p.break_even_revenue)} "
          f"(запас по трафику {-be_p.break_even_traffic_pct:.1f}% от нового уровня)")
    if res.turned_unprofitable:
        print("    ⚠️ Сценарий уводит месяц в убыток!")
    else:
        print("    ✅ В сценарии бизнес остаётся прибыльным.")

    print("\n✅ LTV/чек и сценарии «что если» работают.")


if __name__ == "__main__":
    main()
