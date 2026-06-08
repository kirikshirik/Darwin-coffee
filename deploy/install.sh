#!/usr/bin/env bash
#
# Установка Darwin Coffee на VPS (Ubuntu/Debian + systemd).
# Запускать ОТ ROOT из корня склонированного репозитория:
#
#     sudo APP_DIR=/opt/darwin APP_USER=darwin bash deploy/install.sh
#
# Идемпотентно: можно прогонять повторно при обновлении (см. DEPLOY.md → «Обновление»).
# Перед запуском должен существовать заполненный .env (иначе скрипт остановится и подскажет).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/darwin}"
APP_USER="${APP_USER:-darwin}"
PY="${PY:-python3}"
SYNC_DAYS="${SYNC_DAYS:-30}"   # окно первого (полного) синка

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

log() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mОШИБКА: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Запускай через sudo/от root (нужно создать пользователя и юниты systemd)."
command -v "$PY" >/dev/null || die "$PY не найден. Поставь: apt install -y python3 python3-venv"

# 1) Системный пользователь без логина
if ! id "$APP_USER" >/dev/null 2>&1; then
  log "Создаю системного пользователя $APP_USER"
  useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

# 2) Размещаем код в APP_DIR (если запускаем не из него)
if [ "$REPO_DIR" != "$APP_DIR" ]; then
  log "Копирую код $REPO_DIR → $APP_DIR"
  mkdir -p "$APP_DIR"
  # rsync без .git/.venv/БД, чтобы не тащить мусор и не затереть прод-БД
  rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude 'darwin.db*' --exclude '__pycache__' \
    "$REPO_DIR"/ "$APP_DIR"/
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# 3) .env обязателен
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  die "Создан $APP_DIR/.env из примера. Заполни EVOTOR_CLOUD_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID и запусти скрипт снова."
fi
chmod 600 "$APP_DIR/.env"

# 4) venv + зависимости (от имени APP_USER)
log "Создаю venv и ставлю зависимости"
sudo -u "$APP_USER" "$PY" -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

# 5) Инициализация БД (только если её ещё нет — seed ДЕСТРУКТИВЕН, см. DEPLOY.md)
if [ ! -f "$APP_DIR/darwin.db" ]; then
  log "Первичное наполнение БД (seed)"
  sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m backend.seed
  log "Первый синк Эвотора за $SYNC_DAYS дн."
  sudo -u "$APP_USER" bash -c "cd '$APP_DIR' && .venv/bin/python -m backend.integrations.evotor.sync --days $SYNC_DAYS" \
    || echo "⚠️  Первый синк не прошёл — проверь EVOTOR_CLOUD_TOKEN. Юниты всё равно поставлю; синк повторится по таймеру."
else
  log "БД уже есть — seed пропускаю (чтобы не стереть данные)"
fi

# 6) Рендер и установка юнитов systemd
log "Устанавливаю юниты systemd"
for unit in darwin-bot.service darwin-sync.service darwin-sync.timer; do
  sed -e "s#__APP_DIR__#$APP_DIR#g" -e "s#__APP_USER__#$APP_USER#g" \
    "$APP_DIR/deploy/$unit" > "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now darwin-bot.service
systemctl enable --now darwin-sync.timer

log "Готово. Проверка:"
echo "  systemctl status darwin-bot.service --no-pager"
echo "  systemctl list-timers darwin-sync.timer --no-pager"
echo "  journalctl -u darwin-bot.service -f"
echo ""
echo "Бот: напиши ему /start в Telegram. Синк пойдёт по таймеру каждые 15 минут."
