# Архитектура

Технический разбор: модули, схема БД, финансовая модель и почему сделано именно так.
Обзор проекта — в [HANDOFF.md](HANDOFF.md).

---

## 1. Модули и ответственность

```
backend/
├── db.py                  # инфраструктура БД
├── models.py              # доменная модель (таблицы + ExpenseCategory)
├── darwin_data.py         # реальный P&L «Дарвина» (источник правды из Excel)
├── cost_reference.py      # справочник себестоимости напитков (из Excel фуд-коста)
├── actuals_data.py        # факт ФОТ + Food cost (overlay над darwin_data)
├── honest_report.py       # честный P&L наложением факта на Excel
├── financial/
│   └── profit_calculator.py   # бизнес-логика расчёта прибыли (чистая, без БД)
├── integrations/evotor/   # клиент Облака Эвотор (Фаза 1)
│   ├── client.py          #   async REST (эндпоинты/авторизация сверены с докой)
│   ├── mapping.py         #   ответ Эвотора → Product/Receipt/ReceiptItem + апсерт в БД
│   ├── config.py          #   токен/URL/заголовки из .env
│   ├── exceptions.py      #   EvotorConfig/Auth/APIError
│   ├── sample_data.py     #   образцы ответа (offline)
│   └── demo.py            #   offline-проверка маппинга (без токена)
├── bot/                   # Telegram-бот + планировщик (Фаза 3)
│   ├── metrics.py         #   метрики периодов через ProfitCalculator (чистый, без aiogram)
│   ├── formatting.py      #   рендер текста отчётов (чистый)
│   ├── reports.py         #   БД → metrics → текст (для кнопок и рассылки)
│   ├── handlers.py        #   aiogram: /start + кнопки
│   ├── scheduler.py       #   APScheduler: утренняя сводка
│   ├── main.py            #   точка входа (поллинг)
│   └── demo.py            #   offline-проверка отчётов (без токена)
├── analytics/             # прогноз + «вау»-аналитика (Фаза 4)
│   ├── forecast.py        #   прогноз месяца: run-rate по чекам + историческая модель
│   ├── insights.py        #   топ по прибыли, часы, неделя-к-неделе, рейтинг бариста
│   └── demo.py            #   offline-проверка на образцах за 2 недели
├── seed.py                # наполнение БД из darwin_data
├── report_demo.py         # сборка: БД → калькулятор → отчёт + сверка с Excel
└── cost_demo.py           # себестоимость напитков + аудит цен + проверка Находки 1
```

Принцип: **`ProfitCalculator` не знает про БД.** Он принимает выручку и словарь расходов,
возвращает `ProfitReport`. Это делает его легко тестируемым и переиспользуемым: и
`report_demo`, и бот (`bot/metrics.py`) зовут одну и ту же логику. Модули `bot/metrics`,
`bot/formatting`, маппинг Эвотора — **чистые** (без aiogram/сети), поэтому проверяются
offline (`*/demo.py`) ещё до получения токенов.

Поток данных:
```
Excel (владелец)  ──ручной перенос──▶  darwin_data.py ──seed.py──▶ БД (расходы)
                                                                      │
Эвотор API ──EvotorClient──▶ mapping.sync_* ──▶ БД (чеки/товары) ─────┤
(/stores,/products,/documents; X-Authorization; v2)                   ▼
                                              bot/metrics ─▶ ProfitCalculator ─▶ ProfitReport
                                                                      │ bot/formatting
                                                                      ▼
                                                  Telegram (кнопки + утренняя рассылка)
```
Статус: каркасы Эвотора и бота готовы и проверены offline; ждут Cloud Token и токен бота.

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
| cashier | str(255), nullable | бариста (= `user_id` Эвотора), для рейтинга бариста (Фаза 4) |

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

## 6. Себестоимость напитков (`cost_reference.py`)

Реализовано как **отдельный расчётный модуль** (не БД-таблицы) — из реального Excel
фуд-коста владельца (сводка в `себестоимость.md`).

Состав:
- `BASE_DRINKS` — себестоимость компонентов порции для базовых кофейных позиций по
  объёму (250/350/450 мл). Значения 1:1 из Excel, поэтому сумма сходится с контролем.
- `ADDONS` — допы (какао, матча, сироп, …), прибавляются к базе.
- `ADDONS_NO_COST` — допы без заполненной себестоимости (сливки, арахисовая паста) —
  в расчёт не берутся.
- `CONTROL` — контрольные итоги из Excel (67.82/77.45/79.24 ₽); `verify_against_excel()`
  сверяет (аналог `EXCEL_ANNUAL` в `darwin_data`).
- `audit_input_prices()` — сверяет заявленные закупочные цены (кофе 2200 ₽/кг и т.п.) с
  per-portion суммами; вскрывает несостыковки (кофе округляют, цена корицы спорна).

### Почему модуль, а не БД-таблицы (Ingredient/Recipe/Supplier) — пока
Исходные данные организованы **по объёму стакана**, а не по конкретным напиткам, и у нас
ещё нет: каталога товаров (придёт из Эвотора), привязки напиток→объём+допы, и цен продажи.
Заводить БД-рецепты сейчас = выдумывать данные. Поэтому себестоимость живёт в проверенном
модуле, а БД-таблицы появятся, когда Эвотор даст каталог товаров, а владелец — рецепты и
цены продажи. Тогда `product.cost_price` станет вычисляемым → честная маржа по каждому
напитку (уровень мини-ERP).

---

## 7. Интеграция с Эвотором (`integrations/evotor/`)

REST-клиент Облака Эвотор. **Главное: эндпоинты и авторизация сверены с официальной
докой** (developer.evotor.ru), а не взяты из брейншторма `info` — там пути были выдуманы.

| Что | Значение (проверено) |
|---|---|
| Base URL | `https://api.evotor.ru` |
| Авторизация | заголовок `X-Authorization: <cloud_token>` — **СЫРОЙ токен, без `Bearer`** |
| Версия API | media-type `Accept: application/vnd.evotor.v2+json` (не через путь) |
| Магазины | `GET /stores` |
| Товары | `GET /stores/{id}/products` (пагинация: `cursor` → `paging.next_cursor`) |
| Документы | `GET /stores/{id}/documents` (`since`/`until` в мс, `type=SELL,…`, `cursor`) |

Документ продажи: `type="SELL"`, `close_date` (ISO 8601), `body.positions[]`
(`product_name`, `quantity`, `price`, `result_sum`), `body.result_sum`, `body.payments[]`.

Разделение ответственности:
- `client.py` — только HTTP (async httpx, пагинация, маппинг ошибок в `EvotorAuthError`/
  `EvotorAPIError`). Не знает про БД и Decimal.
- `mapping.py` — чистые функции `dict → Product/Receipt/ReceiptItem` + идемпотентный
  апсерт (`sync_products`, `sync_sales`). Деньги → `Decimal`. **Себестоимость берём из
  своего справочника, а не из Эвотора** (в `/products` нет `cost_price` — подтверждено докой).
- `config.py` — токен/URL/заголовки из `.env`; имя заголовка и схема вынесены, чтобы
  переключиться на OAuth (`Authorization: Bearer`) без правок кода.

Чего НЕ знаем без реального токена (проверить на первых ~100 чеках — это и есть цель Фазы 1):
единицы денег (рубли/копейки → флаг `MONEY_IN_KOPECKS`), точные имена части полей,
доступность метода на тарифе кофейни. Поэтому `_get_any`/`_money` устойчивы к разнобою,
а маппинг проверен offline на `sample_data` (`demo.py`).

---

## 8. Telegram-бот + планировщик (`bot/`)

Доставка продукта владельцу. **Вся арифметика — через `ProfitCalculator`**, бот ничего
не считает сам (метрики собираются в `bot/metrics.py`).

Слои (нижние — чистые, проверяются offline без aiogram):
- `metrics.py` — агрегаты за период: из чеков Эвотора (день/неделя) и честный помесячный
  P&L из Excel (`honest_month` **зеркалит** `honest_report`; `bot/demo.py` сверяет годовой
  итог = 334 651 ₽). Операционка помесячная → для дневных отчётов раскидывается по дням.
- `formatting.py` — текст отчёта (HTML parse_mode).
- `reports.py` — связка БД→metrics→текст для каждой кнопки и для утренней рассылки.
- `handlers.py` / `scheduler.py` / `main.py` — aiogram-роутер, APScheduler-джоба, поллинг.

Дизайн-решения:
- «Месяц» и «Расходы» работают **уже сейчас** на Excel-данных (honest P&L) — headline-ценность
  без Эвотора. Дневные/недельные отчёты включаются автоматически, как пойдут чеки.
- Синхронный SQLAlchemy зовём прямо из async-хендлеров (SQLite-MVP, запросы короткие);
  при переезде на Postgres/нагрузку обернуть в `asyncio.to_thread`.
- Утренняя рассылка не ставится, если не задан `TELEGRAM_OWNER_CHAT_ID` (бот работает по кнопкам).

---

## 9. Прогноз и «вау»-аналитика (`analytics/`)

Чистые модули поверх `bot.metrics` (значит — поверх `ProfitCalculator`). Без сети/aiogram,
проверяются offline (`analytics/demo.py`). Встроены в бота кнопками «Прогноз»/«Аналитика»
и строкой прогноза в утренней сводке.

### `forecast.py` — прогноз месяца
Две модели, выбор по наличию данных (`forecast_month` берёт лучшую доступную):
- **run-rate по чекам** — есть чеки текущего месяца: выручка и COGS экстраполируются по
  числу прошедших дней (`× дней_в_месяце / прошло_дней`), **операционка остаётся
  фиксированной** (она помесячная, не растёт с днями) → реалистичный прогноз прибыли.
- **историческая** — чеков нет (Эвотор не подключён): среднее честной прибыли/выручки за
  последние N месяцев накопленной истории + «тот же месяц год назад» и разброс min…max.
  Работает уже сейчас на реальных данных; для будущего месяца фикс. расходы берём из
  последнего известного месяца.

### `insights.py` — инсайты по чекам (окно по умолчанию 2 недели)
- **Топ по прибыли** — позиции по сумме `ReceiptItem.profit` (не по выручке).
- **Прибыльные часы** — группировка чеков по `sold_at.hour`.
- **Неделя-к-неделе** — `metrics.week_report` за эту и прошлую неделю, % изменения.
- **Рейтинг бариста** — группировка по `Receipt.cashier`. ⚠️ сейчас это raw `user_id`
  Эвотора; имя резолвится через employees-эндпоинт (TODO) — пока показываем как есть.

Прогноз и инсайты по чекам наполняются автоматически, как только пойдут реальные данные
из Эвотора; до этого историческая модель прогноза уже даёт ценность владельцу.
