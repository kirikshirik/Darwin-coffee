# 🚀 Docker — Быстрый старт за 2 минуты

## За 3 команды запустить приложение локально

### 1. Убедиться, что Docker установлен

```bash
docker --version
# Docker version 24.0.0 или выше
```

Если не установлен: [Docker Desktop](https://www.docker.com/products/docker-desktop)

### 2. Собрать и запустить контейнер

```bash
cd /Users/kirillus/Documents/Darwin-coffee
./docker-run.sh up build
```

**Первый запуск** (~3-5 минут):
- Скачиваются образы (Node.js, Python)
- Собирается React фронтенд
- Устанавливаются зависимости Python
- Инициализируется БД
- Запускается приложение

**Ожидаемый вывод в конце:**
```
darwin-coffee  | Web-сервер слушает 0.0.0.0:8000
darwin-coffee  | Polling bot is running
```

### 3. Открыть в браузере

```
http://localhost:8000/app
```

✅ **Готово!** Приложение работает локально в Docker с **полным функционалом**:
- ✅ Telegram-бот подключен и готов к работе
- ✅ Интеграция с Эвотор API активна
- ✅ Синхронизация данных каждые 15 минут
- ✅ Утренняя сводка в 09:00 (МСК)

---

## Следующие запуски (в 10 секунд)

```bash
./docker-run.sh up
# или просто
docker-compose up
```

## Полезные команды

```bash
# Логи (live)
./docker-run.sh logs

# Вход в контейнер (bash)
./docker-run.sh shell

# Остановка (БД сохраняется)
./docker-run.sh down

# Все команды
./docker-run.sh help
```

## Если что-то не работает

| Проблема | Решение |
|----------|---------|
| Port 8000 занят | Измени в `docker-compose.yml`: `ports: ["8001:8000"]` |
| Медленная сборка | Нормально для первого раза (~5 мин). Дальше из cache. |
| БД не инициализирована | `./docker-run.sh shell` → `python -m backend.seed` |
| Нужен Telegram бот | Отредактируй `docker-compose.yml` → `TELEGRAM_BOT_TOKEN`, пересобери |

## Дополнительно

- **Полная документация**: [DOCKER.md](DOCKER.md)
- **Архитектура проекта**: [CLAUDE.md](CLAUDE.md)
- **Production на Render**: [deploy/RENDER.md](deploy/RENDER.md)

---

**На что это влияет:**
- Теперь можно развивать и тестировать локально **без установки Python/Node.js/PostgreSQL**
- Production-like окружение (всё в контейнере)
- Одна команда → готовое приложение
