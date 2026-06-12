# Docker — локальный запуск Darwin Coffee

Готовый Docker контейнер с полным приложением: React фронтенд + Python бэкенд + SQLite БД.

## Требования

- **Docker Desktop** (Mac/Windows) или **Docker + Docker Compose** (Linux)
- Ничего больше не требуется — ни Python 3.9+, ни Node.js, ни npm

## Быстрый старт

### 1️⃣ Первый запуск (сборка контейнера)

```bash
# В корне проекта
docker-compose up --build

# или если используешь встроенный Docker Desktop:
docker compose up --build
```

Будет:
1. Скачан Node.js образ → собран React фронтенд (`npm build`)
2. Скачан Python 3.11 образ → установлены зависимости
3. Инициализирована SQLite БД (`backend.seed`)
4. Запущен Telegram-бот + health-сервер

Ожидаемый вывод:
```
darwin-coffee  | Web-сервер слушает 0.0.0.0:8000 (/, /healthz, /dashboard, /api/dashboard)
darwin-coffee  | Polling bot is running
```

### 2️⃣ Открыть приложение

```
http://localhost:8000/app
```

Фронтенд:
- React в `/app`
- API прокси на `http://localhost:8000/api/*`

API эндпоинты:
- `GET /healthz` — проверка здоровья (для Docker health check)
- `GET /api/dashboard?period=7д` — JSON данные панели
- `POST /api/sync` — синх с Эвотором (если токен задан)

### 3️⃣ Повторные запуски (контейнер уже собран)

```bash
docker-compose up
```

БД сохраняется между рестартами в локальной папке `./data/` и файле `./darwin.db`.

## Конфигурация

### Переменные окружения (в `docker-compose.yml`)

```yaml
environment:
  PORT: 8000                                                       # Порт приложения
  TELEGRAM_BOT_TOKEN: "8516787277:AAFAVUcFQD9a2b1Ck..."          # ✅ Telegram-бот подключен
  TELEGRAM_OWNER_CHAT_ID: "483262851,6726726002"                 # ✅ Владельцы: Кирилл + ?
  TELEGRAM_TZ: Europe/Moscow
  EVOTOR_CLOUD_TOKEN: "eb303f2b-b3a8-4669-a738-afb3d6877485"     # ✅ Эвотор API активен
  DASHBOARD_TOKEN: "26d4JUdiyevwBrZ6sWT6FV5nusEnGY7A"             # ✅ Дашборд защищен токеном
  WEBAPP_URL: "http://localhost:8000/app"
```

**✅ Токены уже подключены** — полный функционал готов к использованию:
- Telegram-бот пингует владельцев
- Синхронизация данных из Эвотора каждые 15 минут
- Утренняя сводка в 09:00 (МСК)
- Дашборд доступен по ссылке с секретным ключом

### Использование Postgres (вместо SQLite)

В `docker-compose.yml` раскомментируй сервис `postgres` и измени:

```yaml
environment:
  DATABASE_URL: postgresql://darwin:localdev123@postgres:5432/darwin_coffee
```

Затем:
```bash
docker-compose up --build
```

Postgres будет доступен на `localhost:5432` для локального подключения.

## Команды

### Остановить контейнер

```bash
docker-compose down
```

БД останется на диске (в `./data/` и `./darwin.db`).

### Удалить всё (включая БД и образы)

```bash
docker-compose down -v --rmi all
```

### Просмотреть логи

```bash
docker-compose logs -f
```

Фильтр по сервису:
```bash
docker-compose logs -f darwin-coffee
```

### Войти в контейнер (shell)

```bash
docker-compose exec darwin-coffee bash
```

Пример: проверить БД изнутри:
```bash
docker-compose exec darwin-coffee sqlite3 darwin.db ".tables"
```

### Пересоздать контейнер (очистить cache)

```bash
docker-compose up --build --force-recreate
```

### Скопировать БД из контейнера на хост

```bash
docker-compose cp darwin-coffee:/app/darwin.db ./darwin-backup.db
```

## Развитие (dev mode)

Если хочешь править код и сразу видеть изменения **без пересборки**:

1. **Бэкенд**: в контейнер смонтируется вся папка `/app` → изменения в `.py` файлах видны сразу (если в коде нет жёсткого кеша)
2. **Фронтенд**: нужна пересборка (Docker не поддерживает hot-reload Vite из контейнера через volume mount — просто запускай локально)

**Лучше для dev:**
```bash
# Локально
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

cd frontend && npm install && npm run dev
# Откроется http://localhost:5173 с hot-reload

# В другом терминале
.venv/bin/python -m backend.seed
.venv/bin/python -m backend.bot.main
# или для быстрого тестирования:
.venv/bin/python -m backend.report_demo
```

Docker → для production-like тестирования.

## Проблемы и FAQ

### ❌ `docker: command not found`

Установи [Docker Desktop](https://www.docker.com/products/docker-desktop).

### ❌ Port 8000 уже занят

Измени в `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # 8001 на хосте, 8000 в контейнере
```

Открой: `http://localhost:8001/app`

### ❌ `npm ERR! 404`

Неверная версия Node.js или не скачались зависимости. Пересборка:
```bash
docker-compose down -v
docker-compose up --build
```

### ❌ БД пуста (нет данных)

`backend.seed` падает молча. Проверь логи:
```bash
docker-compose logs -f darwin-coffee | grep -i seed
```

Если критично, пересоздай:
```bash
docker-compose exec darwin-coffee python -m backend.seed
docker-compose restart
```

### ❌ Медленно собирается

Первая сборка скачивает образы (~1-2 мин на медленном интернете). Последующие — из cache (~10сек).

## На Render (production)

Для деплоя на free Render используй существующий `render.yaml` (не Docker):

```bash
git push origin feat/dynamic-costing-and-scenarios
# На GitHub → Render подхватит render.yaml и деплойнет автоматически
```

Рендер строит контейнер **автоматически** из Dockerfile (если он есть) или из `buildCommand` в `render.yaml`.

## Ссылки

- [Docker Compose docs](https://docs.docker.com/compose/)
- [Render deployment](deploy/RENDER.md)
- [CLAUDE.md](CLAUDE.md) — архитектура приложения
