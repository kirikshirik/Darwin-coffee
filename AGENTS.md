# AGENTS.md — контекст для AI-моделей

Этот файл читают AI-агенты (Claude Code, Cursor, и др.). Для Gemini CLI скопируй его в
`GEMINI.md`. Полная документация — в [docs/](docs/).

## Старт
**Сначала прочитай [docs/HANDOFF.md](docs/HANDOFF.md)** — там полный контекст проекта.

## Проект в одном абзаце
Darwin Coffee — аналитика для кофейни «Дарвин» (касса Эвотор). Считает **реальную чистую
прибыль**, а не выручку, и шлёт ежедневный отчёт в Telegram. Стек: Python 3.9+,
SQLAlchemy 2.0, SQLite→PostgreSQL. Бэкенд в `backend/`.

## Команды
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m backend.seed         # наполнить БД реальными данными
.venv/bin/python -m backend.report_demo  # P&L + сверка с Excel (должно быть ✅ СОВПАДАЕТ)
```

## Правила (важно)
- **Источник правды** — `backend/darwin_data.py` и `.xlsx`-файлы. Файл `info` — это сырой
  брейншторм с устаревшим/ошибочным кодом и **выдуманными эндпоинтами Эвотора**; не копировать оттуда.
- **Пустая ячейка ≠ 0.** Пропуск = «данные не внесены». Модель и калькулятор это различают.
- После правок модели/калькулятора прогоняй `report_demo` — итог обязан остаться `✅ СОВПАДАЕТ`
  с Excel (выручка 3 733 684 ₽, прибыль 899 565 ₽).
- Деньги — только `Decimal`, не `float`.
- Эндпоинты Эвотора сверять с https://developer.evotor.ru, не доверять файлу `info`.

## Где что
| Документ | О чём |
|---|---|
| [docs/HANDOFF.md](docs/HANDOFF.md) | обзор, статус, как запустить, правила |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | схема БД, модули, дизайн-решения |
| [docs/DATA.md](docs/DATA.md) | реальные данные, находки, маппинг Excel |
| [docs/ROADMAP.md](docs/ROADMAP.md) | план, открытые вопросы, блокеры |
