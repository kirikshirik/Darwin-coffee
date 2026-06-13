"""Образцы ответов Облака Эвотор — для offline-разработки и тестов БЕЗ токена.

Структура повторяет официальную доку (поля /stores, /products, документ SELL).
Это НЕ реальные данные «Дарвина» — это синтетика, чтобы прогонять маппинг и бот,
пока не получен Cloud Token (блокер №1). Когда придут первые реальные ответы —
сверить с ними имена полей и единицы денег (см. mapping.MONEY_IN_KOPECKS).
"""
from __future__ import annotations

STORE_ID = "20210301-A1B2-40C3-80D4-DARWINSTORE01"

STORES = [
    {"id": STORE_ID, "name": "Кофейня «Дарвин»", "address": "—"},
]

# user_id документа — id АККАУНТА Эвотора (один на все чеки); кассир — close_user_id
# (UUID сотрудника из /employees). Проверено на живых данных, см. mapping.map_receipt.
ACCOUNT_USER_ID = "01-000000000000001"
EMP_ANNA = "20260101-AAAA-4000-8000-EMP0000000001"
EMP_IGOR = "20260101-BBBB-4000-8000-EMP0000000002"

EMPLOYEES = [
    {"id": EMP_ANNA, "name": "Анна", "last_name": "Соколова", "role": "CASHIER",
     "stores": [STORE_ID], "user_id": ACCOUNT_USER_ID},
    {"id": EMP_IGOR, "name": "Игорь", "last_name": "Ветров", "role": "CASHIER",
     "stores": [STORE_ID], "user_id": ACCOUNT_USER_ID},
]

PRODUCTS = [
    {"id": "PR-CAP-350", "name": "Капучино 350", "price": 220, "parent_id": "GRP-COFFEE",
     "measure_name": "шт", "type": "NORMAL"},
    {"id": "PR-LAT-250", "name": "Латте 250", "price": 200, "parent_id": "GRP-COFFEE",
     "measure_name": "шт", "type": "NORMAL"},
    {"id": "PR-CRO", "name": "Круассан", "price": 130, "parent_id": "GRP-FOOD",
     "measure_name": "шт", "type": "NORMAL"},
]

# Два чека продажи + один возврат (он должен отфильтроваться как не-SELL).
DOCUMENTS = [
    {
        "id": "DOC-0001",
        "type": "SELL",
        "store_id": STORE_ID,
        "user_id": ACCOUNT_USER_ID,
        "close_user_id": EMP_ANNA,
        "close_date": "2026-06-07T08:15:30.000+0000",
        "body": {
            "result_sum": 350,
            "positions": [
                {"product_name": "Капучино 350", "quantity": 1, "price": 220, "result_sum": 220},
                {"product_name": "Круассан", "quantity": 1, "price": 130, "result_sum": 130},
            ],
            "payments": [{"type": "ELECTRON", "sum": 350}],
        },
    },
    {
        "id": "DOC-0002",
        "type": "SELL",
        "store_id": STORE_ID,
        "user_id": ACCOUNT_USER_ID,
        "close_user_id": EMP_IGOR,
        "close_date": "2026-06-07T09:02:11.000+0000",
        "body": {
            "result_sum": 400,
            "positions": [
                {"product_name": "Латте 250", "quantity": 2, "price": 200, "result_sum": 400},
            ],
            "payments": [{"type": "CASH", "sum": 400}],
        },
    },
    {
        "id": "DOC-0003",
        "type": "PAYBACK",  # возврат — маппинг продаж должен его пропустить
        "store_id": STORE_ID,
        "user_id": ACCOUNT_USER_ID,
        "close_user_id": EMP_ANNA,
        "close_date": "2026-06-07T10:30:00.000+0000",
        "body": {
            "result_sum": 220,
            "positions": [
                {"product_name": "Капучино 350", "quantity": 1, "price": 220, "result_sum": 220},
            ],
            "payments": [{"type": "ELECTRON", "sum": 220}],
        },
    },
]

# Контроль для demo: выручка по двум SELL-чекам = 350 + 400.
EXPECTED_SALES_COUNT = 2
EXPECTED_REVENUE = 750

# Цены товаров по имени — чтобы собирать чеки-образцы без ручного дублирования сумм.
_PRICE = {p["name"]: p["price"] for p in PRODUCTS}


def _sell(doc_id: str, when: str, cashier: str, items: list) -> dict:
    """Собрать SELL-документ в схеме Эвотора. items = [(имя, кол-во), …]."""
    positions = []
    total = 0
    for name, qty in items:
        price = _PRICE[name]
        res = price * qty
        total += res
        positions.append(
            {"product_name": name, "quantity": qty, "price": price, "result_sum": res}
        )
    return {
        "id": doc_id,
        "type": "SELL",
        "store_id": STORE_ID,
        "user_id": ACCOUNT_USER_ID,
        "close_user_id": cashier,
        "close_date": f"{when}.000+0000",
        "body": {
            "result_sum": total,
            "positions": positions,
            "payments": [{"type": "ELECTRON", "sum": total}],
        },
    }


# Богатый набор чеков за две недели (8–14 и 1–7 июня) — для Фазы 4 (часы, неделя-к-неделе,
# рейтинг бариста). Разные часы и два бариста (Анна/Игорь). НЕ реальные данные.
DOCUMENTS_WEEK = [
    # --- прошлая неделя (01–07 июня) ---
    _sell("W-101", "2026-06-02T08:20:00", EMP_ANNA,  [("Капучино 350", 1), ("Круассан", 1)]),
    _sell("W-102", "2026-06-02T09:10:00", EMP_IGOR, [("Латте 250", 2)]),
    _sell("W-103", "2026-06-04T08:45:00", EMP_ANNA,  [("Капучино 350", 2)]),
    _sell("W-104", "2026-06-05T13:30:00", EMP_IGOR, [("Латте 250", 1), ("Круассан", 1)]),
    _sell("W-105", "2026-06-06T18:05:00", EMP_ANNA,  [("Капучино 350", 1)]),
    _sell("W-106", "2026-06-07T09:40:00", EMP_IGOR, [("Латте 250", 1), ("Капучино 350", 1)]),
    # --- текущая неделя (08–14 июня) ---
    _sell("W-201", "2026-06-08T08:05:00", EMP_ANNA,  [("Капучино 350", 2), ("Круассан", 2)]),
    _sell("W-202", "2026-06-08T08:50:00", EMP_IGOR, [("Латте 250", 1)]),
    _sell("W-203", "2026-06-09T09:15:00", EMP_ANNA,  [("Капучино 350", 1), ("Латте 250", 1)]),
    _sell("W-204", "2026-06-10T08:30:00", EMP_IGOR, [("Капучино 350", 3)]),
    _sell("W-205", "2026-06-11T12:10:00", EMP_ANNA,  [("Латте 250", 2), ("Круассан", 1)]),
    _sell("W-206", "2026-06-12T08:25:00", EMP_IGOR, [("Капучино 350", 2)]),
    _sell("W-207", "2026-06-13T17:40:00", EMP_ANNA,  [("Латте 250", 1)]),
    _sell("W-208", "2026-06-14T09:05:00", EMP_IGOR, [("Капучино 350", 1), ("Круассан", 1)]),
]

# Опорная «сегодня» для аналитики на DOCUMENTS_WEEK (последний день текущей недели).
ANALYTICS_TODAY = "2026-06-14"
