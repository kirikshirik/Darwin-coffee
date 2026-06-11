"""Точка входа Telegram-бота «Дарвин».

Запуск (нужен TELEGRAM_BOT_TOKEN в .env, см. .env.example):
    .venv/bin/python -m backend.bot.main

Перед первым запуском наполни БД: .venv/bin/python -m backend.seed
Логику отчётов можно проверить без токена: .venv/bin/python -m backend.bot.demo
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from backend.bot.access import OwnerOnlyMiddleware
from backend.bot.config import BotConfig
from backend.bot.handlers import router
from backend.bot.health import start_health_server
from backend.bot.scheduler import setup_scheduler
from backend.seed import ensure_seeded

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("darwin.bot")


async def run() -> None:
    config = BotConfig.from_env()  # бросит BotConfigError без токена

    # Схема + данные накатываются идемпотентно: на VPS с готовой SQLite это no-op,
    # на свежей облачной БД (Neon) — создаёт таблицы и засевает бизнес/расходы.
    ensure_seeded()

    bot = Bot(token=config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    # Доступ только владельцам (там финансы) — одно место на все хендлеры.
    dp.message.middleware(OwnerOnlyMiddleware(config.owner_chat_ids))
    dp.include_router(router)

    scheduler = setup_scheduler(bot, config)

    # На Render/PaaS задан $PORT — поднимаем health-сервер (нужен для деплоя и keepalive).
    # На VPS PORT нет → сервер не нужен, порты наружу не открываем.
    port = os.getenv("PORT")
    health_runner = await start_health_server(int(port)) if port else None

    log.info("Бот «Дарвин» запущен (поллинг).")
    try:
        await dp.start_polling(bot)
    finally:
        if health_runner is not None:
            await health_runner.cleanup()
        scheduler.shutdown(wait=False)
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Остановка по Ctrl+C.")


if __name__ == "__main__":
    main()
