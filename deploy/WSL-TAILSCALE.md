# Самохостинг: Windows 10 + WSL2 + Tailscale Funnel

Третий путь деплоя (после VPS — [DEPLOY.md](../DEPLOY.md) и Render — [RENDER.md](RENDER.md)):
бот живёт на своём ноутбуке в WSL2 Ubuntu под systemd, БД — локальный SQLite,
Mini App доступен владельцам через публичный HTTPS от Tailscale Funnel.

```
Telegram ←поллинг (исходящий)── бот (WSL2, systemd) ──► SQLite /opt/darwin/darwin.db
Телефоны владельцев ─► https://darwin-bot.<tailnet>.ts.net (Funnel, публичный HTTPS)
                        └─► tailscaled (внутри WSL) ─► 127.0.0.1:8000 (aiohttp)
```

Tailscale ставится **внутри WSL**, а не на Windows: funnel проксирует прямо на
localhost дистрибутива — не нужны `netsh portproxy` и борьба с дрейфом IP WSL.

⚠️ **Перед стартом**: репозиторий публичный, токены в него не вписывать. Если токены
когда-либо попадали в git — перевыпустить (бот: /revoke у @BotFather; Эвотор: ЛК;
DASHBOARD_TOKEN: просто сгенерировать новый, например `openssl rand -base64 24`).

---

## 1. Windows 10

1. WSL2: в PowerShell (админ) `wsl --install -d Ubuntu`, затем `wsl --update`
   (systemd требует WSL ≥ 0.67.4).
2. Не дать ноуту спать (от сети):
   ```powershell
   powercfg /change standby-timeout-ac 0
   powercfg /change hibernate-timeout-ac 0
   ```
   Панель управления → Электропитание → «Действие при закрытии крышки» → **Ничего не делать**.
3. Автозапуск после ребута:
   - `netplwiz` → автологин пользователя Windows;
   - Планировщик заданий → создать задачу «При входе в систему»:
     программа `wsl.exe`, аргументы `-d Ubuntu --exec /bin/true`
     (поднимает дистро → systemd сам стартует бота и tailscaled).
4. Windows Update: выставить активные часы, чтобы не было ночных перезагрузок.

## 2. WSL2 Ubuntu: бот под systemd

1. Включить systemd — в WSL:
   ```bash
   sudo tee /etc/wsl.conf >/dev/null <<'EOF'
   [boot]
   systemd=true
   EOF
   ```
   В PowerShell: `wsl --shutdown`, открыть Ubuntu заново,
   проверить: `systemctl is-system-running` (running/degraded — ок).
2. Пакеты и код:
   ```bash
   sudo apt update && sudo apt install -y git python3-venv python3-pip rsync curl
   git clone https://github.com/kirikshirik/Darwin-coffee.git && cd Darwin-coffee
   git checkout feat/evotor-bot-analytics
   ```
3. Заполнить `.env` (скрипт сам создаст из примера и остановится при первом прогоне):
   ```
   TELEGRAM_BOT_TOKEN=…
   TELEGRAM_OWNER_CHAT_ID=…           # один или несколько id через запятую
   EVOTOR_CLOUD_TOKEN=…
   DASHBOARD_TOKEN=…                  # запасной вход в дашборд из браузера (?key=…)
   PORT=8000                          # ВКЛЮЧАЕТ веб-сервер (/app, /api, /dashboard)
   EVOTOR_SYNC_INTERVAL_MIN=15        # синк внутри процесса бота (как на Render)
   WEBAPP_URL=https://darwin-bot.<tailnet>.ts.net/app   # подставить URL из шага 3.3
   TELEGRAM_TZ=Europe/Moscow
   TELEGRAM_REPORT_TIME=09:00
   # DATABASE_URL не задавать → SQLite /opt/darwin/darwin.db (WAL уже настроен)
   ```
4. Установка (готовый скрипт VPS-пути, работает и в WSL2):
   ```bash
   sudo APP_DIR=/opt/darwin APP_USER=darwin SYNC_DAYS=365 bash deploy/install.sh
   ```
   `SYNC_DAYS=365` затягивает всю историю чеков из Эвотора с нуля (товары,
   сотрудники, чеки) — миграцию данных с Neon делать не нужно.
5. Синк уже идёт внутри процесса (`EVOTOR_SYNC_INTERVAL_MIN`), поэтому
   systemd-таймер не нужен — отключить, чтобы не синкать дважды:
   ```bash
   sudo systemctl disable --now darwin-sync.timer
   ```

## 3. Tailscale Funnel

1. Внутри WSL:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --hostname darwin-bot
   ```
2. В админке https://login.tailscale.com: включить **HTTPS Certificates**
   и **Funnel** (админка сама предложит добавить nodeAttrs в ACL).
3. Опубликовать порт:
   ```bash
   sudo tailscale funnel --bg 8000
   tailscale funnel status     # покажет https://darwin-bot.<tailnet>.ts.net
   ```
4. Вписать этот URL в `WEBAPP_URL` в `/opt/darwin/.env` (+ `/app` на конце) и
   `sudo systemctl restart darwin-bot`.

## 4. Переключение прода (порядок важен!)

Два поллинга одним токеном рвут друг друга (`TelegramConflictError`):

1. **Сначала** Suspend сервиса `darwin-bot` в дашборде Render
   (env-переменные не трогать — это холодный резерв).
2. Потом на ноуте: `sudo systemctl enable --now darwin-bot`.
3. Если есть UptimeRobot — перенацелить монитор на
   `https://darwin-bot.<tailnet>.ts.net/healthz`: теперь это алерт «ноутбук упал».

## 5. Бэкапы SQLite

Ежедневный консистентный снимок (WAL-безопасный) + ротация 30 дней — cron от root:

```cron
20 4 * * * install -d -o darwin /opt/darwin/backups && sudo -u darwin /opt/darwin/.venv/bin/python -c "import sqlite3,datetime; sqlite3.connect('/opt/darwin/darwin.db').execute(\"VACUUM INTO '/opt/darwin/backups/darwin-%s.db'\" % datetime.date.today())" && find /opt/darwin/backups -name 'darwin-*.db' -mtime +30 -delete
```

Чеки/товары/сотрудники восстановимы ресинком из Эвотора (`sync --days 365`),
критичны только ручные расходы — их и бережём.

---

## Проверка (сквозная)

| # | Проверка | Ожидание |
|---|---|---|
| 1 | `systemctl status darwin-bot` | active (running) |
| 2 | `curl -s localhost:8000/healthz` | `ok` |
| 3 | `curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/dashboard` | `401` (TMA-auth работает) |
| 4 | С телефона на мобильном интернете: `https://darwin-bot.<tailnet>.ts.net/app` | страница открывается, данных без Telegram не отдаёт |
| 5 | В Telegram `/dashboard` → кнопка | Mini App открывается, данные грузятся |
| 6 | `journalctl -u darwin-bot -f` (≤15 мин) | строка о плановом синке, нет TelegramConflictError |
| 7 | Перезагрузить Windows | через ~2 мин всё поднялось само |
| 8 | Следующее утро 09:00 МСК | сводка пришла владельцам |

## Риски

- **Win10 без обновлений (EOL)** — наружу торчит только Funnel (443 через
  инфраструктуру Tailscale); RDP/SMB и прочее наружу не открывать.
- **Свет/электричество** — UPS нет: при отключении бот молчит. Резерв — вручную
  включить (Resume) сервис на Render; ноут при этом обязательно остановить
  (`systemctl stop darwin-bot`), иначе конфликт поллинга.
- **Funnel** идёт через релеи Tailscale — скорость ограничена, для дашборда хватает.
