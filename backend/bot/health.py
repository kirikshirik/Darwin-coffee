"""Минимальный HTTP health-сервер — для PaaS вроде Render.

Render (free web service) требует, чтобы процесс слушал порт из $PORT, иначе деплой
считается неудачным, и усыпляет сервис после 15 мин без входящих запросов. Поэтому:
  • поднимаем крошечный сервер, отвечающий 200 на «/» и «/healthz»;
  • внешний пингер (UptimeRobot, бесплатно) дёргает «/healthz» каждые ~5 мин —
    входящий трафик не даёт сервису заснуть, и бот-поллинг продолжает жить.

На VPS переменной PORT нет → сервер не поднимается, поведение не меняется (см. main.py).
"""
from __future__ import annotations

import logging

from aiohttp import web

log = logging.getLogger(__name__)


async def _ok(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_health_server(port: int) -> web.AppRunner:
    """Поднять health-сервер на 0.0.0.0:port. Вернуть runner для остановки (cleanup)."""
    app = web.Application()
    app.router.add_get("/", _ok)
    app.router.add_get("/healthz", _ok)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("Health-сервер слушает 0.0.0.0:%d (/, /healthz)", port)
    return runner
