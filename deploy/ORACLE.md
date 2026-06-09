# Деплой на бесплатную VM Oracle Cloud (Always Free)

Как развернуть «Дарвина» (Telegram-бот + синк Эвотора) на **бесплатной навсегда**
виртуалке Oracle Cloud. Это не триал и не кредиты — Always Free-ресурсы не
списывают деньги, пока ты в их лимитах.

Боту **не нужны входящие порты**: поллинг ([backend/bot/main.py](../backend/bot/main.py))
ходит к Telegram только наружу. Дашборд тоже не хостится — бот отдаёт его файлом по
команде `/dashboard`. Значит, на VM открыт лишь SSH, наружу больше ничего не торчит.

Этот гайд закрывает **Oracle-специфику** (регистрация + создание VM). Дальше установка
и эксплуатация — общие, см. [DEPLOY.md](../DEPLOY.md).

```
Эвотор API ──(sync.timer, 15 мин)──▶ darwin.db ◀──(читает)── Telegram-бот ──▶ владелец
                                                                  │
                                                          /dashboard → HTML-файл
```

---

## 1. Аккаунт Oracle Cloud

1. Регистрация: **https://www.oracle.com/cloud/free/** → «Start for free».
2. Нужны почта, телефон и **банковская карта** — только для верификации, **списаний
   нет** (Always Free не превращается в платный сам по себе).
3. **Регион (Home Region) выбирается один раз и навсегда** — бери ближайший доступный.
   Для РФ обычно Frankfurt / Amsterdam / Stockholm. На скорость бота это не влияет
   (он общается с Telegram и Эвотором, задержка незаметна).

## 2. Создать Always Free VM

Console → **Compute → Instances → Create instance**:

1. **Image:** Canonical **Ubuntu 24.04** (или 22.04).
2. **Shape (тип машины)** — выбери Always Free:
   - **VM.Standard.A1.Flex** (ARM Ampere) — поставь **1 OCPU / 6 GB RAM**. Лучший вариант.
   - Если выскочит **«Out of host capacity»** (для A1 в популярных регионах частое) —
     переключись на **VM.Standard.E2.1.Micro** (AMD, 1 OCPU / 1 GB). Их всегда два
     бесплатных и они почти всегда доступны. Для одного бота 1 GB достаточно.
3. **SSH-ключи:** выбери «Paste public keys». Сгенерируй ключ **на своём Маке** и
   вставь содержимое `.pub`:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/darwin_oracle -C darwin-oracle -N ""
   cat ~/.ssh/darwin_oracle.pub      # это вставить в Oracle
   ```
4. **Networking:** оставь дефолт — Oracle создаст VCN с публичной подсетью. В Security
   List по умолчанию открыт **только SSH (22)** — это всё, что нужно. **Никакие другие
   порты не открывай.**
5. Boot volume — дефолт (≈47–50 GB) ок.
6. **Create**. Дождись статуса *Running* и запиши **Public IP**.

## 3. Подключиться по SSH

У образов Ubuntu от Canonical пользователь по умолчанию — `ubuntu`:

```bash
ssh -i ~/.ssh/darwin_oracle ubuntu@<PUBLIC_IP>
```

Базовые пакеты (на VM):

```bash
sudo apt update && sudo apt install -y python3 python3-venv rsync git
```

## 4. Положить код на VM

**Вариант A — из GitHub** (если репозиторий запушен):

```bash
sudo git clone <URL_РЕПОЗИТОРИЯ> /opt/darwin
# приватный репозиторий: используй deploy key или https с PAT
```

**Вариант B — rsync со своего Мака** (без GitHub; запускать **на Маке**, из корня проекта):

```bash
rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude 'darwin.db*' --exclude '__pycache__' \
  -e "ssh -i ~/.ssh/darwin_oracle" \
  ./ ubuntu@<PUBLIC_IP>:/tmp/darwin/
# затем на VM:
sudo mkdir -p /opt/darwin && sudo rsync -a /tmp/darwin/ /opt/darwin/
```

## 5. Заполнить `.env`

Создай `/opt/darwin/.env` **до** запуска install.sh (так скрипт не споткнётся об
отсутствующий `.env.example`). Минимум — три значения:

```bash
sudo tee /opt/darwin/.env >/dev/null <<'ENV'
# --- Telegram-бот ---
TELEGRAM_BOT_TOKEN=        # от @BotFather
TELEGRAM_OWNER_CHAT_ID=    # от @userinfobot — ОБЯЗАТЕЛЬНО для /dashboard и утренней сводки
TELEGRAM_TZ=Europe/Moscow
TELEGRAM_REPORT_TIME=09:00

# --- Эвотор (Облако) ---
EVOTOR_CLOUD_TOKEN=        # облачный токен из кабинета разработчика Эвотора (можно позже)
EVOTOR_TZ=Europe/Moscow

# --- БД ---
# По умолчанию SQLite (хватает на одну кофейню). Postgres — опционально, см. DEPLOY.md §6.
# DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/darwin
ENV
sudo nano /opt/darwin/.env    # вписать реальные токены
```

- **`TELEGRAM_OWNER_CHAT_ID` обязателен:** без него `/dashboard` отвечает «команда
  выключена» (финансовую панель некому доверить), а утренняя рассылка не ставится.
- **`EVOTOR_CLOUD_TOKEN`** можно оставить пустым на старте — бот заработает в демо-режиме
  на данных из Excel; синк подключишь позже, заполнив токен и перезапустив сервис.

## 6. Установка

```bash
cd /opt/darwin
sudo APP_DIR=/opt/darwin APP_USER=darwin bash deploy/install.sh
```

`install.sh` идемпотентен: создаёт пользователя `darwin`, ставит venv + зависимости,
наполняет БД (seed — **только если её ещё нет**), делает первый синк и поднимает
systemd-юниты (`darwin-bot.service` + `darwin-sync.timer`). Подробности и повторный
деплой — [DEPLOY.md §2–4](../DEPLOY.md).

## 7. Проверка

```bash
systemctl status darwin-bot.service --no-pager
systemctl list-timers darwin-sync.timer --no-pager
journalctl -u darwin-bot.service -n 50 --no-pager     # ждём «Run polling…» и «Планировщик запущен»
```

В Telegram: напиши боту `/start`, понажимай кнопки, затем `/dashboard` — придёт свежий
`darwin_dashboard.html` (открыть в браузере). Полный список проверок — [DEPLOY.md §3](../DEPLOY.md).

---

## 8. Грабли именно Oracle

- **«Out of host capacity» на A1.Flex.** Попробуй другой Availability Domain в форме
  создания, повтори чуть позже или возьми **E2.1.Micro** (см. §2).
- **Аккаунт могут «заморозить» при полном простое.** Постоянно работающий бот этот
  простой исключает — рисков нет.
- **Два слоя фаервола.** У Oracle это VCN Security List (облако) **и** локальный iptables
  в образе Ubuntu. Нам открывать ничего не нужно (бот исходящий), поэтому оба слоя
  трогать не надо — оставь как есть, только SSH.
- **Таймзона `Europe/Moscow`.** На минимальном образе tz-базы может не быть; пакет
  `tzdata` уже в [requirements.txt](../requirements.txt), ставится в venv автоматически.
- **`TelegramConflictError: terminated by other getUpdates`** — значит, бот с тем же
  токеном запущен где-то ещё (часто забытый процесс на Маке). Должен жить один экземпляр.

## 9. Обновление и бэкап

Не дублирую — см. [DEPLOY.md §4 «Обновление»](../DEPLOY.md) (повторный `install.sh`
не трогает `darwin.db` и `.env`) и [§8 «Бэкап»](../DEPLOY.md) (вся БД — один файл
`darwin.db`).
