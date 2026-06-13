"""HTTP-сервер сервиса: health-проверки + публикация ops-панели по секретной ссылке.

1. health (/ и /healthz) — Render (free web service) требует слушать $PORT, иначе
   деплой неуспешен, и усыпляет сервис без входящих запросов. UptimeRobot пингует
   /healthz → бот-поллинг продолжает жить. На VPS PORT нет → сервер не поднимается.

2. /dashboard — отдаёт СВЕЖУЮ ops-панель (тот же build_html, что у команды бота),
   за секретным токеном DASHBOARD_TOKEN: ?key=<токен>. Данные финансовые, поэтому:
   нет токена в env → маршрут выключен (404); неверный ключ → 403; ответу ставим
   X-Robots-Tag: noindex, чтобы не попал в поисковики.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse

from aiohttp import web

from backend import dashboard

log = logging.getLogger(__name__)

# Фоновое автообновление «при открытии дашборда»: на Render free сервис засыпает в
# простое → плановый синк (bot/scheduler.py) встаёт. Чтобы данные были свежими при
# просмотре, дёргаем инкрементальный синк Эвотора фоном, если давно не синкали.
# _last_sync=None → первый просмотр после сна/рестарта всегда триггерит синк.
_last_sync: float | None = None
_sync_lock = asyncio.Lock()


async def _maybe_bg_sync() -> None:
    """Fire-and-forget синк Эвотора, если данные устарели. Ответ дашборда не блокирует."""
    global _last_sync
    if not os.getenv("EVOTOR_CLOUD_TOKEN", "").strip():
        return
    try:
        interval = int(os.getenv("EVOTOR_SYNC_INTERVAL_MIN", "15") or 15)
    except ValueError:
        interval = 15
    if interval <= 0 or _sync_lock.locked():
        return
    if _last_sync is not None and time.monotonic() - _last_sync < interval * 60:
        return
    _last_sync = time.monotonic()

    async def _run() -> None:
        from backend.integrations.evotor import sync as evotor_sync
        async with _sync_lock:
            try:
                await asyncio.to_thread(evotor_sync.sync, 3)
                log.info("Фоновый синк Эвотора (при открытии дашборда) выполнен")
            except Exception:
                log.exception("Фоновый синк при открытии дашборда не прошёл")

    asyncio.create_task(_run())


async def _ok(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def _dashboard(request: web.Request) -> web.Response:
    token = os.getenv("DASHBOARD_TOKEN", "").strip()
    if not token:
        return web.Response(status=404, text="Not found")
    if request.query.get("key", "") != token:
        return web.Response(status=403, text="Доступ запрещён: неверный или отсутствует ключ.")
    await _maybe_bg_sync()  # автообновление данных Эвотора фоном — ответ не задерживает
    try:
        # SystemExit ловим явно: build_html → render() так сигналит о незаполненном шаблоне.
        # Таймаут 25сек — Neon free tier может просыпаться >15сек на cold start
        period = request.query.get("period", "7д")
        html = await asyncio.wait_for(asyncio.to_thread(dashboard.build_html, period), timeout=25)
    except asyncio.TimeoutError:
        log.warning("ops-панель собиралась >25сек (завис?); вероятно медленные DB-запросы или Neon холодный старт")
        return web.Response(status=503, text="Сервис перегружен: сборка панели заняла >25сек. Повторите запрос через минуту.")
    except (Exception, SystemExit):
        log.exception("Не удалось собрать ops-панель для веба")
        return web.Response(status=500, text="Не удалось собрать панель — смотри логи.")
    return web.Response(
        text=html,
        content_type="text/html",
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )


async def _sync(request: web.Request) -> web.Response:
    from backend.integrations.evotor import sync
    denied = _authorize(request)
    if denied is not None:
        return denied
    try:
        await asyncio.to_thread(sync.sync)
        return web.json_response({"status": "ok"})
    except Exception as e:
        log.exception("Ошибка при синхронизации")
        return web.json_response({"status": "error", "message": str(e)}, status=500)


def validate_telegram_data(init_data: str, bot_token: str) -> bool:
    """Проверить подпись initData Telegram Mini App (HMAC по схеме WebAppData)."""
    if not init_data or not bot_token:
        return False
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data))
        if 'hash' not in parsed:
            return False
        received_hash = parsed.pop('hash')
        data_check = '\n'.join(f'{k}={v}' for k, v in sorted(parsed.items()))
        secret = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
        computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, received_hash)
    except Exception as e:
        log.warning(f"Ошибка валидации auth data: {e}")
        return False


# initData живёт в клиенте Telegram между открытиями Mini App; перехваченная строка
# не должна работать вечно — старше суток не принимаем (Mini App при открытии выдаёт свежую).
MAX_INITDATA_AGE_SEC = 24 * 60 * 60


def _authorize(request: web.Request) -> web.Response | None:
    """Доступ к финансовым API: ?key=<DASHBOARD_TOKEN> или подпись Telegram Mini App.

    Подпись initData подтверждает лишь, что данные выдал Telegram для нашего бота, —
    но не что это владелец. Поэтому дополнительно сверяем user.id со списком
    TELEGRAM_OWNER_CHAT_ID (тот же, что у OwnerOnlyMiddleware бота) и свежесть auth_date.
    Возвращает None при допуске, иначе — готовый ответ 401/403.
    """
    dash_token = os.getenv("DASHBOARD_TOKEN", "").strip()
    if dash_token and request.query.get("key", "") == dash_token:
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("tma "):
        return web.json_response({"error": "Нет авторизации — откройте панель через Telegram-бота."}, status=401)
    init_data = auth_header[4:]
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not validate_telegram_data(init_data, bot_token):
        return web.json_response({"error": "Недействительная подпись Telegram."}, status=403)

    parsed = dict(urllib.parse.parse_qsl(init_data))
    try:
        auth_age = time.time() - int(parsed.get("auth_date", "0"))
    except ValueError:
        auth_age = MAX_INITDATA_AGE_SEC + 1
    if not 0 <= auth_age <= MAX_INITDATA_AGE_SEC:
        return web.json_response({"error": "Сессия устарела — переоткройте Mini App."}, status=403)

    from backend.bot.config import parse_owner_ids
    owners = parse_owner_ids(os.getenv("TELEGRAM_OWNER_CHAT_ID", ""))
    if owners:
        try:
            user_id = int(json.loads(parsed.get("user", "{}")).get("id", 0))
        except (ValueError, TypeError, json.JSONDecodeError):
            user_id = 0
        if user_id not in owners:
            return web.json_response({"error": "Доступ только для владельцев."}, status=403)
    else:
        log.warning("TELEGRAM_OWNER_CHAT_ID не задан — /api/* доступен любому пользователю бота")
    return None


async def _api_dashboard(request: web.Request) -> web.Response:
    denied = _authorize(request)
    if denied is not None:
        return denied
    await _maybe_bg_sync()  # после сна Render данные могли устареть — обновляем фоном
    period = request.query.get("period", "7д")
    try:
        # to_thread + таймаут — как у /dashboard: синхронный вызов compute_json держал бы
        # весь event loop (поллинг бота, /healthz) на холодном старте Neon (>15сек)
        data = await asyncio.wait_for(asyncio.to_thread(dashboard.compute_json, period), timeout=25)
        return web.json_response(data)
    except asyncio.TimeoutError:
        log.warning("/api/dashboard собирался >25сек (Neon холодный старт?)")
        return web.json_response({"error": "Сервис просыпается, повторите через минуту."}, status=503)
    except Exception as e:
        log.exception("Ошибка в /api/dashboard")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def start_health_server(port: int) -> web.AppRunner:
    """Поднять веб-сервер на 0.0.0.0:port. Вернуть runner для остановки (cleanup)."""
    app = web.Application()
    app.router.add_get("/", _ok)
    app.router.add_get("/healthz", _ok)
    app.router.add_get("/dashboard", _dashboard)
    app.router.add_get("/api/dashboard", _api_dashboard)
    app.router.add_post("/api/sync", _sync)
    
    # Serve React Frontend
    import pathlib
    ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
    FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
    frontend_available = False
    if FRONTEND_DIST.exists():
        frontend_available = True
        app.router.add_static("/assets", FRONTEND_DIST / "assets")

        # Serve static files (favicon, icons, etc)
        for file in FRONTEND_DIST.iterdir():
            if file.is_file() and file.name != "index.html":
                async def static_handler(request, path=file):
                    return web.FileResponse(path)
                app.router.add_get(f"/{file.name}", static_handler)

        # Serve React app at /app (SPA — all routes go to index.html)
        async def index_handler(request):
            return web.FileResponse(FRONTEND_DIST / "index.html")
        app.router.add_get("/app", index_handler)
        app.router.add_get("/app/{path_info:.*}", index_handler)
        
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    dash = "токен задан" if os.getenv("DASHBOARD_TOKEN", "").strip() else "выключен (нет DASHBOARD_TOKEN)"
    frontend_status = "✓ React /app" if frontend_available else "(фронтенд не собран)"
    log.info("Web-сервер слушает 0.0.0.0:%d (/, /healthz, /dashboard, /api/dashboard, %s) — %s", port, frontend_status, dash)
    return runner
