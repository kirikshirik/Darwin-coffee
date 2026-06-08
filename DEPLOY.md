# Деплой на VPS

Гайд по развёртыванию «Дарвина» на одном VPS (Ubuntu 22.04/24.04 или Debian 12).
Всё держится на двух юнитах systemd:

- **`darwin-bot.service`** — Telegram-бот: кнопки + утренняя сводка в 09:00. Работает постоянно, перезапускается сам.
- **`darwin-sync.timer`** → **`darwin-sync.service`** — тянет чеки/товары из Эвотора в БД каждые 15 минут.

База — **SQLite** (`darwin.db`) с включённым WAL: бот читает, синк пишет, друг другу не мешают. Для одной кофейни этого достаточно; PostgreSQL — опционально (см. ниже).

```
Эвотор API ──(sync.timer, 15 мин)──▶ darwin.db ◀──(читает)── Telegram-бот ──▶ владелец
```

---

## 1. Что нужно

- VPS с Ubuntu/Debian, root или sudo.
- Python 3.9+ (`apt install -y python3 python3-venv rsync git`).
- Токены: **Cloud Token Эвотора**, **токен бота** от @BotFather, **chat_id** владельца (узнать у @userinfobot).

## 2. Установка (быстрый путь)

```bash
# на VPS под root/sudo
apt update && apt install -y python3 python3-venv rsync git

# код проекта (git clone или scp/rsync с локалки)
git clone <ВАШ_РЕПО> /opt/darwin
cd /opt/darwin

# секреты
cp .env.example .env
nano .env        # заполнить EVOTOR_CLOUD_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID

# установка: venv + зависимости + seed + первый синк + юниты systemd
sudo APP_DIR=/opt/darwin APP_USER=darwin bash deploy/install.sh
```

`install.sh` идемпотентен и сам:
создаёт системного пользователя `darwin`, ставит venv и зависимости, наполняет БД (`seed`, **только если её ещё нет**), делает первый синк за 30 дней, рендерит юниты под ваши пути и поднимает сервис + таймер.

> Если `.env` ещё не заполнен — скрипт создаст его из примера и остановится с подсказкой. Заполните и запустите снова.

## 3. Проверка

```bash
systemctl status darwin-bot.service --no-pager
systemctl list-timers darwin-sync.timer --no-pager
journalctl -u darwin-bot.service -n 50 --no-pager     # лог бота
journalctl -u darwin-sync.service -n 50 --no-pager    # лог последнего синка
```

В логе бота должно быть `Run polling for bot @<имя>` и `Планировщик запущен`. Затем напишите боту `/start` в Telegram и нажмите кнопки.

---

## 4. Эксплуатация

| Действие | Команда |
|---|---|
| Логи бота вживую | `journalctl -u darwin-bot.service -f` |
| Перезапустить бота | `systemctl restart darwin-bot.service` |
| Синк прямо сейчас | `systemctl start darwin-sync.service` |
| Когда следующий синк | `systemctl list-timers darwin-sync.timer` |
| Остановить всё | `systemctl stop darwin-bot.service darwin-sync.timer` |

### Обновление кода (redeploy)

```bash
cd /path/to/local/checkout && git pull         # или обновите /opt/darwin
sudo APP_DIR=/opt/darwin APP_USER=darwin bash deploy/install.sh
systemctl restart darwin-bot.service
```

Повторный `install.sh` обновит код (через `rsync`, **не трогая `darwin.db` и `.env`**), переставит зависимости и юниты. `seed` повторно НЕ запускается, если БД уже есть.

---

## 5. ⚠️ Важно: что НЕ запускать на проде

`backend.seed` и `backend.bot.demo` вызывают `drop_all()` — **полностью стирают БД** (включая синхронизированные чеки) и наполняют тестовыми данными. На боевом сервере их запускать нельзя.

Безопасно для проверки: `python -m backend.integrations.evotor.demo` (в БД не пишет).

---

## 6. PostgreSQL (опционально)

SQLite+WAL тянет одну кофейню. Если нужен Postgres (несколько точек, внешний доступ):

```bash
apt install -y postgresql
sudo -u postgres createuser darwin --pwprompt
sudo -u postgres createdb darwin -O darwin

# в venv:
/opt/darwin/.venv/bin/pip install "psycopg[binary]>=3.1"

# в .env:
DATABASE_URL=postgresql+psycopg://darwin:ПАРОЛЬ@localhost:5432/darwin
```

Затем `python -m backend.seed` (создаст схему) и первый синк. Дальше — как обычно.

---

## 7. Траблшутинг

- **`TelegramConflictError: terminated by other getUpdates`** — где-то запущен второй экземпляр бота с тем же токеном (часто — забытый локальный процесс). Оставьте один: `pkill -f backend.bot.main` на лишней машине.
- **`database is locked`** — не должно быть при WAL; если появляется, проверьте, что БД на локальном диске (не на сетевом NFS), и что не запущено несколько писателей.
- **`ZoneInfoNotFoundError: Europe/Moscow`** — нет tz-базы: `pip install tzdata` (уже в requirements.txt) или `apt install -y tzdata`.
- **Бот молчит / нет утренней сводки** — проверьте `TELEGRAM_OWNER_CHAT_ID` в `.env` (без него рассылка выключена) и `journalctl -u darwin-bot.service`.
- **Пустые отчёты «Нет чеков»** — синк не прошёл: `systemctl start darwin-sync.service` и смотрите `journalctl -u darwin-sync.service` (чаще всего — неверный `EVOTOR_CLOUD_TOKEN`).

## 8. Бэкап

Один файл: `darwin.db`. Безопасная копия с учётом WAL:

```bash
sudo -u darwin /opt/darwin/.venv/bin/python - <<'PY'
import sqlite3, pathlib
src = sqlite3.connect("/opt/darwin/darwin.db")
src.execute("VACUUM INTO '/opt/darwin/darwin.backup.db'")
PY
```

Положите эту команду в cron — и БД будет копироваться целиком и консистентно.
