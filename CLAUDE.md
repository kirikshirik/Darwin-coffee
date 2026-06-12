# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Документация проекта на русском. Отвечай и комментируй код по-русски.
> Полный контекст — в [docs/HANDOFF.md](docs/HANDOFF.md) (точка входа),
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATA.md](docs/DATA.md),
> [docs/ROADMAP.md](docs/ROADMAP.md). [AGENTS.md](AGENTS.md)/[GEMINI.md](GEMINI.md) —
> те же инструкции для других AI-агентов; держи их в синхроне при правках правил.

## Что это

AI-аналитика для кофейни «Дарвин» (касса Эвотор), которая считает **реальную чистую
прибыль**, а не выручку, и шлёт ежедневный отчёт владельцу в Telegram. Продукт строится на
реальных данных одной кофейни, перенесённых из Excel владельца в код.

## Команды

```bash
# Окружение (Python 3.9+)
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Наполнить БД реальными данными (drop+create, идемпотентно)
.venv/bin/python -m backend.seed

# --- Проверка/«тесты»: pytest нет, верификация = offline demo-скрипты ---
.venv/bin/python -m backend.report_demo            # P&L + сверка с Excel → "✅ СОВПАДАЕТ"
.venv/bin/python -m backend.cost_demo              # себестоимость напитков + аудит цен
.venv/bin/python -m backend.honest_report          # честный P&L (реальный ФОТ+COGS)
.venv/bin/python -m backend.integrations.evotor.demo   # маппинг Эвотора (без токена)
.venv/bin/python -m backend.bot.demo               # отчёты бота (без токена)
.venv/bin/python -m backend.analytics.demo         # прогноз + инсайты
.venv/bin/python -m backend.costing.demo           # динамический фуд-кост / тех-карты
.venv/bin/python -m backend.scenarios.demo         # LTV / средний чек / «что если»

# Запуск бота (нужен TELEGRAM_BOT_TOKEN в .env, см. .env.example)
.venv/bin/python -m backend.bot.main

# Локальный веб-дашборд на http://localhost:8000
.venv/bin/python -m backend.server
```

`backend.*.demo` — это и есть способ проверить логику: каждый печатает строку `✅`
при успехе. Любая правка модели/калькулятора должна оставлять `report_demo` зелёным.

### БД и деплой
- БД по умолчанию — SQLite (`darwin.db`, WAL). Прод — Postgres через `DATABASE_URL`
  (`postgresql://…` нормализуется в `psycopg`-драйвер автоматически, см. [backend/db.py](backend/db.py)).
- VPS (systemd: бот + sync-таймер) — [DEPLOY.md](DEPLOY.md). Бесплатный Render+Neon —
  [deploy/RENDER.md](deploy/RENDER.md) / [render.yaml](render.yaml).

## Архитектура (большая картина)

Ядро — **`ProfitCalculator`** ([backend/financial/profit_calculator.py](backend/financial/profit_calculator.py)):
не знает про БД, принимает выручку + словарь расходов, возвращает `ProfitReport` с маржами
и `warnings`. Всю арифметику (бот, дашборд, прогноз, сценарии) гоняют через него — нигде
не считают деньги «сбоку».

Слоистость: нижние модули **чистые** (`Decimal`, без БД/сети/aiogram) → проверяются offline
через `*/demo.py` ещё до получения внешних токенов. Сетевые/БД-слои тонкие сверху.

Поток данных:
```
Excel владельца ──(ручной перенос)──▶ backend/darwin_data.py ──seed──▶ БД (расходы)
Эвотор API ──EvotorClient──▶ mapping.sync_* ──▶ БД (чеки/товары)
                                  └─▶ bot/metrics ─▶ ProfitCalculator ─▶ отчёт ─▶ Telegram / дашборд
```

Карта модулей `backend/`:
- `models.py` — таблицы + `ExpenseCategory` (Enum хранится **по имени члена**, не по русской строке).
- `darwin_data.py` / `cost_reference.py` / `actuals_data.py` — **источники правды** из Excel
  (P&L / себестоимость напитков / факт ФОТ+COGS). `honest_report.py` накладывает факт на P&L.
- `integrations/evotor/` — async REST-клиент Облака Эвотор (`client.py`) + маппинг в БД (`mapping.py`).
- `bot/` — aiogram-бот + APScheduler (утренняя сводка). `metrics`/`formatting` — чистые.
- `analytics/` — прогноз месяца + инсайты. `costing/` — динамические тех-карты/ингредиенты/списания.
  `scenarios/` — LTV/средний чек + «что если»/break-even. Все три — поверх `ProfitCalculator`, чистые.
- `dashboard.py` / `server.py` / `invest_landing.py` — генерация HTML-дашборда и инвест-лендинга.

## Правила (важно — нарушение ломает суть продукта)

- **Источник правды по данным** — `darwin_data.py`, `cost_reference.py`, `actuals_data.py`
  и `.xlsx` в `reference/`. Файл `reference/info` — сырой брейншторм с устаревшим/ошибочным
  кодом и **выдуманными эндпоинтами Эвотора**; не копировать оттуда.
- **`MONTHLY` в `darwin_data.py` — это копия 1:1 P&L-Excel** (контроль: выручка 3 733 684 ₽,
  прибыль 899 565 ₽). Не править его фактом из дневного отчёта — реальные ФОТ/COGS живут
  отдельно в `actuals_data.py` и накладываются в `honest_report` (честная прибыль ≈ 334 651 ₽/год).
- После правок модели/калькулятора прогоняй `report_demo` — итог обязан остаться `✅ СОВПАДАЕТ`.
- **Пустая ячейка ≠ 0.** Пропуск = «данные не внесены», а не «расход = 0». Модель и
  калькулятор это различают (на этом стоят авто-проверки качества данных) — сохраняй поведение.
- **Деньги — только `Decimal` / `Numeric(12,2)`**, никогда `float`.
- Эндпоинты/авторизацию Эвотора сверять с https://developer.evotor.ru
  (`X-Authorization` — сырой токен без `Bearer`; media-type `v2`), а не с файлом `info`.
- Себестоимость ведём сами (`cost_reference.py` / `costing/`) — Эвотор `cost_price` не отдаёт.
- БД-таблицы рецептов (Ingredient/Recipe) намеренно отложены, пока нет каталога товаров из
  Эвотора и цен продажи (см. ARCHITECTURE §6) — не заводить их «вперёд данных».
