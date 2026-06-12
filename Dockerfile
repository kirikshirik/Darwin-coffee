# Многоэтапная сборка: Node.js для фронтенда, Python для бэкенда

# Этап 1: сборка React фронтенда
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# Копируем фронтенд
COPY frontend ./

# Устанавливаем зависимости и собираем
RUN npm ci && npm run build

# Этап 2: Python приложение с собранным фронтенда
FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для psycopg (PostgreSQL драйвер)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь бэкенд и корневые конфиги
COPY backend ./backend
COPY *.py ./
# reference/ в .gitignore — не копируем

# Копируем собранный фронтенд из первого этапа
COPY --from=frontend-builder /build/dist ./frontend/dist

# Создаём SQLite БД директорию (если нужна локальная БД)
RUN mkdir -p /app/data

# Открываем порт (default 8000, но на Render может быть $PORT)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

# Инициализируем БД (если не существует) и запускаем приложение
CMD bash -c "python -m backend.seed && python -m backend.bot.main"
