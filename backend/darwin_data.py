"""Реальные данные кофейни «Дарвин» — единый источник правды.

Перенесено 1:1 из Excel-файлов владельца:
  • «Финансовые показатели new_26.xlsx» — помесячный P&L (июнь 2025 — май 2026)
  • «Таблица оценки мат.активов (1).xlsx» — оценка оборудования

Пустые ячейки в Excel НЕ заменяются нулём, а просто отсутствуют в словаре —
это принципиально: так калькулятор отличает «расход = 0» от «данные не внесены»
(например, ФОТ пуст в 6 месяцах из 12).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

from backend.models import ExpenseCategory as C

BUSINESS = {
    "name": "Кофейня «Дарвин»",
    "business_value": D("1100000"),   # оценка стоимости бизнеса
    "equipment_value": D("1000000"),  # оценка оборудования (детально — в таблице активов)
}

# Помесячные данные. Ключи expenses — только реально заполненные в Excel статьи.
MONTHLY = [
    {"period": date(2025, 6, 1), "revenue": D("437059"), "expenses": {
        C.RENT: D("82950"), C.UTILITIES: D("10238"), C.PAYROLL: D("94888"),
        C.TAXES: D("19445"), C.ACQUIRING: D("1295"), C.OTHER: D("191722"),
    }},
    {"period": date(2025, 7, 1), "revenue": D("416770"), "expenses": {
        C.RENT: D("82950"), C.UTILITIES: D("9191"), C.PAYROLL: D("93161"),
        C.TAXES: D("30000"), C.OTHER: D("113323"),
    }},
    {"period": date(2025, 8, 1), "revenue": D("398214"), "expenses": {
        C.RENT: D("82950"), C.UTILITIES: D("9100"), C.PAYROLL: D("85795"),
        C.ACQUIRING: D("1295"), C.OTHER: D("143176"),
    }},
    {"period": date(2025, 9, 1), "revenue": D("283883"), "expenses": {
        C.RENT: D("82950"), C.UTILITIES: D("11300"), C.OTHER: D("78080"),
        # ФОТ не внесён
    }},
    {"period": date(2025, 10, 1), "revenue": D("346343"), "expenses": {
        C.RENT: D("82950"), C.PAYROLL: D("79952"), C.OTHER: D("113265"),
        # коммунальные не внесены
    }},
    {"period": date(2025, 11, 1), "revenue": D("267754"), "expenses": {
        C.RENT: D("82950"), C.UTILITIES: D("4784"), C.TAXES: D("7978"),
        C.ACQUIRING: D("990"), C.OTHER: D("90127"), C.DEPRECIATION: D("9154"),
        # ФОТ не внесён
    }},
    {"period": date(2025, 12, 1), "revenue": D("325296"), "expenses": {
        C.RENT: D("82950"), C.UTILITIES: D("15943"), C.TAXES: D("29000"),
        C.ACQUIRING: D("918"), C.OTHER: D("72564"), C.DEPRECIATION: D("12930"),
        # ФОТ не внесён
    }},
    {"period": date(2026, 1, 1), "revenue": D("232827"), "expenses": {
        C.RENT: D("84530"), C.UTILITIES: D("13795"), C.TAXES: D("5525"),
        C.ACQUIRING: D("990"), C.OTHER: D("53160"),
        # ФОТ не внесён
    }},
    {"period": date(2026, 2, 1), "revenue": D("204487"), "expenses": {
        C.RENT: D("84530"), C.UTILITIES: D("9889"), C.ACQUIRING: D("990"),
        C.OTHER: D("71576"),
        # ФОТ не внесён
    }},
    {"period": date(2026, 3, 1), "revenue": D("310959"), "expenses": {
        C.RENT: D("84530"), C.UTILITIES: D("9889"), C.PAYROLL: D("80600"),
        C.ACQUIRING: D("1190"), C.OTHER: D("62564"),
    }},
    {"period": date(2026, 4, 1), "revenue": D("203595"), "expenses": {
        C.RENT: D("84530"), C.UTILITIES: D("9135"), C.TAXES: D("5977"),
        C.OTHER: D("55413"),
        # ФОТ не внесён
    }},
    {"period": date(2026, 5, 1), "revenue": D("306497"), "expenses": {
        C.RENT: D("84530"), C.UTILITIES: D("9135"), C.PAYROLL: D("80400"),
        C.TAXES: D("5977"), C.OTHER: D("25000"),
    }},
]

# Контрольные суммы из Excel (строка «Сумма за период 12 мес») — для проверки калькулятора.
EXCEL_ANNUAL = {
    "revenue": D("3733684"),
    "total_expenses": D("2834119"),
    "net_profit": D("899565"),
}
