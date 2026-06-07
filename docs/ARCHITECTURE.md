# Архитектура

Технический разбор: модули, схема БД, финансовая модель и почему сделано именно так.
Обзор проекта — в [HANDOFF.md](HANDOFF.md).

---

## 1. Модули и ответственность

```
backend/
├── db.py                  # инфраструктура БД
├── models.py              # доменная модель (таблицы + ExpenseCategory)
├── darwin_data.py         # реальные данные «Дарвина» (источник правды из Excel)
├── financial/
│   └── profit_calculator.py   # бизнес-логика расчёта прибыли (чистая, без БД)
├── seed.py                # наполнение БД из darwin_data
└── report_demo.py         # сборка: БД → калькулятор → отчёт + сверка с Excel
```

Принцип: **`ProfitCalculator` не знает про БД.** Он принимает выручку и словарь расходов,
возвращает `ProfitReport`. Это делает его легко тестируемым и переиспользуемым (бот, API,
прогноз — все зовут одну и ту же логику).

Поток данных:
```
Excel (владелец)  ──ручной перенос──▶  darwin_data.py
                                            │  seed.py
                                            ▼
Эвотор API (TODO) ──EvotorClient──▶      БД (SQLAlchemy)
                                            │  report_demo.py / бот (TODO)
                                            ▼
                                     ProfitCalculator ──▶ ProfitReport ──▶ Telegram (TODO)
```

---

## 2. Схема БД

Все денежные поля — `Numeric(12, 2)` → Python `Decimal`. Определено в `backend/models.py`.

### `businesses` — кофейня
| Поле | Тип | Заметки |
|---|---|---|
| id | int PK | |
| name | str(255) | «Кофейня «Дарвин»» |
| evotor_store_uuid | str(100), unique, nullable | UUID магазина из Эвотора |
| business_value | Numeric, nullable | оценка стоимости бизнеса |
| equipment_value | Numeric, nullable | оценка оборудования |
| created_at | datetime | server_default=now() |

### `products` — товары/напитки
| Поле | Тип | Заметки |
|---|---|---|
| id | int PK | |
| business_id | FK→businesses | |
| evotor_uuid | str(100), index, nullable | из Эвотора |
| name | str(255) | |
| category | str(255), nullable | |
| sell_price | Numeric | цена продажи |
| **cost_price** | Numeric, default 0 | **себестоимость — Эвотор её обычно не хранит, ведём вручную** |
| active | bool | |

### `receipts` — чеки (из Эвотора)
| Поле | Тип |
|---|---|
| id | int PK |
| business_id | FK→businesses |
| receipt_uuid | str(100), unique, index, nullable |
| sold_at | datetime, index |
| total_sum | Numeric |
| payment_type | str(50), nullable |

### `receipt_items` — позиции в чеке
| Поле | Тип | Заметки |
|---|---|---|
| id | int PK | |
| receipt_id | FK→receipts (cascade delete) | |
| product_id | FK→products, nullable | |
| quantity | Numeric(12,3) | |
| price | Numeric | |
| revenue | Numeric | qty × price |
| cost | Numeric, default 0 | qty × product.cost_price |
| profit | Numeric, default 0 | revenue − cost |

### `expenses` — расходы (ручной ввод владельца)
| Поле | Тип | Заметки |
|---|---|---|
| id | int PK | |
| business_id | FK→businesses | |
| **period** | Date, index | **первое число месяца** (данные ведутся помесячно) |
| category | Enum(ExpenseCategory) | см. ниже |
| amount | Numeric | |
| comment | Text, nullable | |

### `daily_metrics` — готовые дневные агрегаты (то, что шлёт бот)
| Поле | Тип |
|---|---|
| id | int PK |
| business_id | FK→businesses |
| metric_date | Date, index |
| revenue, cogs, gross_profit, operating_expenses, net_profit, avg_check | Numeric |
| checks_count | int |

### Связи
```
Business 1───* Product
Business 1───* Receipt 1───* ReceiptItem *───1 Product
Business 1───* Expense
Business 1───* DailyMetric
```

---

## 3. ExpenseCategory — статьи расходов

`str`-Enum в `models.py`. Значения — ровно как в Excel владельца. В БД хранится
**имя члена** (RENT, PAYROLL, …), не русская строка.

| Член | Русское название |
|---|---|
| `COGS` | Себестоимость (закупка товара) — *в Excel НЕТ, спрятана в «Прочее»* |
| `RENT` | Аренда |
| `UTILITIES` | Коммунальные |
| `PAYROLL` | Затраты на персонал |
| `TAXES` | Налоги |
| `MARKETING` | Маркетинг и реклама |
| `ACQUIRING` | Эквайринг и QR-комиссия банка |
| `SOFTWARE` | ПО (CRM, ERP, ОФД) |
| `COMMS_SECURITY` | Телефония, интернет, охрана |
| `OTHER` | Прочее |
| `DEPRECIATION` | Амортизация и ремонт оборудования |

---

## 4. Финансовая модель

```
Выручка
  − Себестоимость (COGS)        = Валовая прибыль      (gross_profit)
  − Операционные расходы         = Чистая прибыль       (net_profit)

Валовая маржа = Валовая прибыль / Выручка
Чистая маржа  = Чистая прибыль / Выручка
```

Реализация — `ProfitCalculator.compute(period, revenue, expenses)`:
- `COGS` = сумма статей из `COGS_CATEGORIES` (сейчас только `ExpenseCategory.COGS`).
- Операционные расходы = все остальные статьи.
- Возвращает `ProfitReport` (dataclass) со всеми цифрами, маржами и списком `warnings`.

### Авто-проверки качества данных (`_check_data_quality`)
- `COGS == 0` → флаг «маржу по товарам не посчитать без справочника себестоимости».
- `PAYROLL == 0` → флаг «ФОТ не внесён, прибыль завышена».
- `OTHER > 20% выручки` → флаг «в «Прочее» вероятно зашита закупка товара».

Именно эти проверки автоматически вскрыли проблемы в данных «Дарвина» (см. [DATA.md](DATA.md)).

---

## 5. Дизайн-решения и почему

| Решение | Причина |
|---|---|
| `ProfitCalculator` без зависимости от БД | тестируемость; одна логика для бота/API/прогноза |
| Деньги `Decimal`/`Numeric`, не `float` | точность копеек, корректная сверка с Excel |
| Пустая ячейка → статья ОТСУТСТВУЕТ (не 0) | различать «нет данных» и «расход 0» — основа проверок качества |
| Enum хранится по имени члена | устойчиво к смене русских формулировок |
| SQLite по умолчанию, Postgres через `DATABASE_URL` | быстрый старт без инфраструктуры |
| Синхронный SQLAlchemy | проще; async добавим в боте/EvotorClient точечно |
| Схема создаётся в `seed.py` (drop+create) | для MVP вместо Alembic; миграции — позже |

---

## 6. Что добавить во второй версии (для расчёта COGS)

Чтобы себестоимость пересчитывалась автоматически при изменении закупочных цен:

```
recipes        # рецепт товара (Капучино = ...)
recipe_items   # 17 г зерна, 200 мл молока, 1 стакан, 1 крышка
suppliers      # закупочные цены ингредиентов
```

Тогда `product.cost_price` становится вычисляемым, а не ручным, и появляется честная
маржа по каждому напитку. Это уже уровень мини-ERP для кофейни.
