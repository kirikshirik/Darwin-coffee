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
import logging
import os
import time

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
        # Таймаут 10сек — если дольше, значит что-то завис (N+1 запросы, медленная Neon, etc)
        period = request.query.get("period", "7д")
        html = await asyncio.wait_for(asyncio.to_thread(dashboard.build_html, period), timeout=10)
    except asyncio.TimeoutError:
        log.warning("ops-панель собиралась >10сек (завис?); вероятно медленные DB-запросы или Neon холодный старт")
        return web.Response(status=503, text="Сервис перегружен: сборка панели заняла >10сек. Повторите запрос через минуту.")
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
    token = os.getenv("DASHBOARD_TOKEN", "").strip()
    if token and request.query.get("key", "") != token:
        return web.Response(status=403, text="Доступ запрещён.")
    try:
        await asyncio.to_thread(sync.sync)
        return web.json_response({"status": "ok"})
    except Exception as e:
        log.exception("Ошибка при синхронизации")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

import urllib.parse
import hmac
import hashlib

def validate_telegram_data(init_data: str, bot_token: str) -> bool:
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

@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.path.startswith("/api/dashboard"):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("tma "):
            init_data = auth_header[4:]
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            if not validate_telegram_data(init_data, bot_token):
                return web.json_response({"error": "Invalid authorization data"}, status=403)
    return await handler(request)

async def _api_dashboard(request: web.Request) -> web.Response:
    period = request.query.get("period", "7д")
    try:
        data = dashboard.compute_json(period)
        return web.json_response(data)
    except Exception as e:
        log.exception("Ошибка в /api/dashboard")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def start_health_server(port: int) -> web.AppRunner:
    """Поднять веб-сервер на 0.0.0.0:port. Вернуть runner для остановки (cleanup)."""
    app = web.Application(middlewares=[auth_middleware])
    app.router.add_get("/", _ok)
    app.router.add_get("/healthz", _ok)
    app.router.add_get("/dashboard", _dashboard)
    app.router.add_get("/api/dashboard", _api_dashboard)
    app.router.add_post("/api/sync", _sync)
    
    # Serve React Frontend
    import pathlib
    ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
    FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
    if FRONTEND_DIST.exists():
        app.router.add_static("/assets", FRONTEND_DIST / "assets")
        for file in FRONTEND_DIST.iterdir():
            if file.is_file() and file.name != "index.html":
                app.router.add_route("GET", f"/{file.name}", lambda r, path=file: web.FileResponse(path))
        
        async def index_handler(request):
            return web.FileResponse(FRONTEND_DIST / "index.html")
        app.router.add_get("/app", index_handler)
        
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    dash = "токен задан" if os.getenv("DASHBOARD_TOKEN", "").strip() else "выключен (нет DASHBOARD_TOKEN)"
    log.info("Web-сервер слушает 0.0.0.0:%d (/, /healthz, /dashboard, /api/dashboard — %s)", port, dash)
    return runner
