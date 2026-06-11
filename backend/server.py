"""Локальный сервер для дашборда.

Запускает aiohttp-сервер на порту 8000, отдаёт сгенерированный дашборд.
Поддерживает параметр period через query (?period=вч|7д|мес).

Запуск:
    python -m backend.server
"""
import asyncio
import logging
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

from backend import dashboard
from backend.integrations.evotor import sync

log = logging.getLogger("darwin.server")

async def handle_dashboard(request: web.Request) -> web.Response:
    period = request.query.get("period", "7д")
    try:
        html = dashboard.build_html(period)
        return web.Response(text=html, content_type="text/html")
    except Exception as e:
        log.exception("Ошибка сборки дашборда")
        return web.Response(status=500, text=f"Ошибка сервера: {e}")

async def handle_sync(request: web.Request) -> web.Response:
    import sys
    try:
        python_path = sys.executable
        proc = await asyncio.create_subprocess_exec(
            python_path, "-m", "backend.integrations.evotor.sync",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            msg = stdout.decode("utf-8").strip()
            log.info(f"Синхронизация Эвотора успешна: {msg}")
            return web.json_response({"status": "ok", "message": msg})
        else:
            err_msg = stderr.decode("utf-8").strip() or stdout.decode("utf-8").strip() or "Неизвестная ошибка"
            log.warning(f"Ошибка синхронизации Эвотора: {err_msg}")
            return web.json_response({"status": "error", "message": err_msg})
    except Exception as e:
        log.exception("Исключение в handle_sync")
        return web.json_response({"status": "error", "message": str(e)})

async def main():
    logging.basicConfig(level=logging.INFO)
    app = web.Application()
    app.router.add_get("/", handle_dashboard)
    app.router.add_post("/api/sync", handle_sync)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    
    log.info("Сервер дашборда запущен на http://localhost:8000")
    log.info("Нажмите Ctrl+C для остановки")
    
    # Бесконечный цикл для удержания сервера
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
