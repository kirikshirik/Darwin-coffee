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

from aiohttp import web

from backend import dashboard

log = logging.getLogger(__name__)


async def _ok(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def _dashboard(request: web.Request) -> web.Response:
    token = os.getenv("DASHBOARD_TOKEN", "").strip()
    if not token:
        return web.Response(status=404, text="Not found")
    if request.query.get("key", "") != token:
        return web.Response(status=403, text="Доступ запрещён: неверный или отсутствует ключ.")
    try:
        # SystemExit ловим явно: build_html → render() так сигналит о незаполненном шаблоне.
        # Таймаут 10сек — если дольше, значит что-то завис (N+1 запросы, медленная Neon, etc)
        html = await asyncio.wait_for(asyncio.to_thread(dashboard.build_html), timeout=10)
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


async def start_health_server(port: int) -> web.AppRunner:
    """Поднять веб-сервер на 0.0.0.0:port. Вернуть runner для остановки (cleanup)."""
    app = web.Application()
    app.router.add_get("/", _ok)
    app.router.add_get("/healthz", _ok)
    app.router.add_get("/dashboard", _dashboard)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    dash = "токен задан" if os.getenv("DASHBOARD_TOKEN", "").strip() else "выключен (нет DASHBOARD_TOKEN)"
    log.info("Web-сервер слушает 0.0.0.0:%d (/, /healthz, /dashboard — %s)", port, dash)
    return runner
