"""Фактические данные «Дарвина» из дневного отчёта — overlay над `darwin_data`.

Источник: «Отчет 25-26.xlsx» — по листу на месяц (октябрь 2025 — май 2026),
дневные строки в диапазоне 2:32. Из него берём ДВА ряда, которых не хватало
в помесячном P&L (`darwin_data.MONTHLY`):

  • ФОТ (колонка G «Зарплата») — закрывает Находку 2: в P&L-Excel зарплаты пусты
    в 6 месяцах из 12, из-за чего прибыль завышена почти вдвое.
  • Food cost (колонка H) — реальная закупка товара = COGS. Закрывает Находку 1:
    в P&L-Excel себестоимость спрятана внутри статьи «Прочее».

Почему overlay, а не правка MONTHLY: `darwin_data.MONTHLY` — это копия 1:1 файла
«Финансовые показатели new_26.xlsx», и `report_demo` обязан сходиться с его
контролем 899 565 ₽. Фактические данные — из ДРУГОГО файла, поэтому держим их
отдельно и считаем «честный» P&L наложением (см. `backend/honest_report.py`).

Сверка: выручка по дням (D2:32) этого файла совпадает с `MONTHLY` до рубля по
всем 8 месяцам — это та же кофейня, данные согласованы.

Деньги — только Decimal.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D
from typing import Dict

SOURCE = "Отчет 25-26.xlsx (дневной отчёт, листы по месяцам; G2:32 — ФОТ, H2:32 — Food cost)"

# Фактические помесячные суммы. payroll — точные данные ФОТ (G2:G32),
# food_cost — реальная закупка товара (COGS, колонка H).
ACTUALS: Dict[date, Dict[str, D]] = {
    date(2025, 10, 1): {"payroll": D("79952"), "food_cost": D("113265")},
    date(2025, 11, 1): {"payroll": D("78387"), "food_cost": D("90127")},
    date(2025, 12, 1): {"payroll": D("83364"), "food_cost": D("115412")},
    date(2026, 1, 1):  {"payroll": D("76741"), "food_cost": D("47713")},
    date(2026, 2, 1):  {"payroll": D("71024"), "food_cost": D("71576")},
    date(2026, 3, 1):  {"payroll": D("82647"), "food_cost": D("62564")},
    date(2026, 4, 1):  {"payroll": D("75179"), "food_cost": D("61390")},
    date(2026, 5, 1):  {"payroll": D("82424"), "food_cost": D("25000")},
}

# Контрольные суммы за период октябрь–май (8 мес.) для самопроверки.
CONTROL = {
    "payroll_total": D("629718"),    # сумма ФОТ за окт–май
    "food_cost_total": D("587047"),  # сумма Food cost за окт–май
}

# Конфликт с P&L-Excel: где в MONTHLY ФОТ всё-таки внесён, он расходится с
# дневным отчётом. Дневной отчёт считаем точным (он на уровне дней).
PAYROLL_CONFLICTS = {
    date(2026, 3, 1): {"monthly": D("80600"), "actual": D("82647")},
    date(2026, 5, 1): {"monthly": D("80400"), "actual": D("82424")},
    # октябрь совпадает (79 952) — конфликта нет.
}

# ФОТ за сентябрь 2025 получен отдельно от владельца (в дневном отчёте его нет).
# Food cost за сентябрь неизвестен → в честном P&L берётся средний реальный food cost
# за период окт–май (см. avg_food_cost), по решению владельца.
PAYROLL_EXTRA: Dict[date, D] = {
    date(2025, 9, 1): D("80600"),
}

# Остаточных пробелов по ФОТ больше нет: окт–май — дневной отчёт, сен 25 — от владельца,
# июн–авг — из P&L-Excel.
PAYROLL_STILL_MISSING: list = []


def verify_control() -> bool:
    """Сумма ACTUALS обязана сходиться с CONTROL (как EXCEL_ANNUAL в darwin_data)."""
    pay = sum((m["payroll"] for m in ACTUALS.values()), D("0"))
    fc = sum((m["food_cost"] for m in ACTUALS.values()), D("0"))
    return pay == CONTROL["payroll_total"] and fc == CONTROL["food_cost_total"]


def food_cost_ratio() -> D:
    """Доля реального food cost в выручке за окт–май (COGS / выручка) ≈ 0.267.

    Единственный обоснованный коэффициент себестоимости из фактических данных.
    Синк Эвотора использует его как прокси COGS позиции (цена × ratio), пока не
    заведено точное сопоставление рецептов к именам товаров (маржа по напиткам).
    """
    from backend import darwin_data  # локальный импорт: overlay не зависит от MONTHLY на уровне модуля

    rev = sum((m["revenue"] for m in darwin_data.MONTHLY if m["period"] in ACTUALS), D("0"))
    return (CONTROL["food_cost_total"] / rev) if rev else D("0")


def avg_food_cost() -> D:
    """Средний реальный food cost за месяц (окт–май), до рубля.

    Оценка COGS для месяцев без дневного отчёта (сейчас — сентябрь 2025).
    587 047 / 8 = 73 381 ₽.
    """
    total = sum((m["food_cost"] for m in ACTUALS.values()), D("0"))
    return (total / len(ACTUALS)).quantize(D("1"))
