# Бесплатный деплой на Render + Neon (без банковской карты)

Развёртывание «Дарвина» на бесплатных тарифах, **где не нужна карта**:

- **Render (free web service)** — держит процесс бота 24/7.
- **Neon (free Postgres)** — внешняя БД (у Render free нет постоянного диска, SQLite не годится).
- **UptimeRobot (free)** — пингует бота, чтобы Render не усыплял сервис.

Все три регистрируются по email/GitHub **без карты**.

```
UptimeRobot ──ping /healthz каждые 5 мин──▶ Render (бот: поллинг + планировщик + health)
                                                   │
                                          DATABASE_URL ▼
                                              Neon (Postgres)
```

> Под капотом один процесс делает всё: Telegram-поллинг, утреннюю сводку, синк Эвотора
> каждые 15 мин и health-эндпоинт. Конфигурация — в [render.yaml](../render.yaml).
> Альтернатива (свой Linux-сервер, SQLite, systemd) — [DEPLOY.md](../DEPLOY.md) / [ORACLE.md](ORACLE.md).

---

## 0. Что нужно заранее

- Репозиторий проекта на **GitHub** (Render деплоит из него).
- Токены: **бот** от @BotFather, **chat_id** владельца от @userinfobot,
  **Cloud Token Эвотора** (можно позже — на старте демо-режим).

## 1. Neon — бесплатный Postgres

1. Регистрация: **https://neon.tech** → Sign up (GitHub/email, без карты).
2. Create project (имя любое, регион — ближе к Render, напр. Frankfurt/EU).
3. Скопируй **Connection string** вида:
   ```
   postgresql://user:pass@ep-xxx.eu-central-1.aws.neon.tech/dbname?sslmode=require
   ```
   Это будущий `DATABASE_URL`. Схему `postgresql://` править не нужно — код сам
   приведёт её к `postgresql+psycopg://` ([backend/db.py](../backend/db.py)).

   > Если Neon показывает «Pooled connection» — бери именно её (стабильнее при
   > авто-засыпании Neon). `sslmode=require` оставь.

## 2. Render — web-сервис из Blueprint

1. Регистрация: **https://render.com** → Sign up with GitHub (без карты).
2. **New → Blueprint**, выбери свой репозиторий. Render подхватит [render.yaml](../render.yaml)
   и создаст сервис `darwin-bot` (free).
3. На шаге переменных заполни те, что помечены `sync:false`:

   | Переменная | Значение |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | токен от @BotFather |
   | `TELEGRAM_OWNER_CHAT_ID` | твой chat_id (@userinfobot) |
   | `DATABASE_URL` | строка подключения Neon из шага 1 |
   | `EVOTOR_CLOUD_TOKEN` | токен Эвотора или **пусто** (демо-режим) |

   Остальные (`EVOTOR_SYNC_INTERVAL_MIN=15`, таймзоны, время сводки) уже заданы в Blueprint.
4. **Apply** / **Create**. Render соберёт зависимости и запустит `python -m backend.bot.main`.

При первом старте бот сам накатит схему и засеет бизнес/расходы в Neon
(`ensure_seeded()` — идемпотентно, повторные рестарты данные не трогают).

## 3. Проверка

- **Logs** в дашборде Render: должны быть `Health-сервер слушает …`,
  `Run polling…` и `Сводка по расписанию…`. Если задан токен Эвотора — ещё
  `Синк Эвотора по расписанию: каждые 15 мин`.
- Открой `https://<твой-сервис>.onrender.com/healthz` → ответ `ok`.
- В Telegram: `/start`, кнопки, затем `/dashboard` → придёт `darwin_dashboard.html`.

## 4. UptimeRobot — не давать сервису заснуть

Free web service Render засыпает после **15 мин** без входящих запросов (тогда
останавливается и поллинг, и сводка). Лечим бесплатным пингером:

1. Регистрация: **https://uptimerobot.com** (без карты).
2. **Add New Monitor** → тип **HTTP(s)**, URL: `https://<твой-сервис>.onrender.com/healthz`,
   интервал **5 минут** (меньше 15 — сервис не успевает заснуть).
3. Сохрани. Теперь бот живёт постоянно.

> Бонус: при падении монитор пришлёт уведомление на почту.

---

## 5. Грабли и нюансы

- **Бесплатный лимит Render — 750 часов/мес** на инстанс: одного сервиса 24/7 хватает
  (≈720 ч). Второй free-сервис уже не уместится в лимит круглосуточно.
- **Холодный старт.** Если UptimeRobot вдруг не пинговал, первый запрос будит сервис
  30–60 сек. С пингом каждые 5 мин этого не происходит.
- **Neon scale-to-zero.** Бесплатная БД засыпает при простое; первый запрос будит её за
  пару секунд. От «протухших» коннектов защищает `pool_pre_ping=True` ([db.py](../backend/db.py)).
- **Деплой нового кода.** `git push` в подключённую ветку → Render пересоберёт сам.
  Данные в Neon при этом не теряются (БД внешняя).
- **`TelegramConflictError: terminated by other getUpdates`** — где-то запущен второй
  экземпляр бота с тем же токеном (часто забытый локальный процесс). Должен жить один.
- **Пересоздать схему/данные с нуля** (ОСТОРОЖНО — сотрёт чеки): из локали с тем же
  `DATABASE_URL` запусти `python -m backend.seed`. Штатно это не нужно — `ensure_seeded()`
  делает всё сам при первом старте.

## 6. Чем этот путь отличается от VPS

| | Render + Neon | VPS / Oracle ([DEPLOY.md](../DEPLOY.md)) |
|---|---|---|
| Карта при регистрации | не нужна | нужна (Oracle) |
| БД | Neon Postgres (внешняя) | SQLite на диске |
| Синк Эвотора | в процессе бота (`EVOTOR_SYNC_INTERVAL_MIN`) | systemd-таймер `darwin-sync.timer` |
| Не уснуть | UptimeRobot пингует `/healthz` | не требуется (постоянный процесс) |
