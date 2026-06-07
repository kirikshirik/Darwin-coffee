"""Точка входа Telegram-бота «Дарвин».

Запуск (нужен TELEGRAM_BOT_TOKEN в .env, см. .env.example):
    .venv/bin/python -m backend.bot.main

Перед первым запуском наполни БД: .venv/bin/python -m backend.seed
Логику отчётов можно проверить без токена: .venv/bin/python -m backend.bot.demo
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from backend.bot.config import BotConfig
from backend.bot.handlers import router
from backend.bot.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("darwin.bot")


async def run() -> None:
    config = BotConfig.from_env()  # бросит BotConfigError без токена

    bot = Bot(token=config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = setup_scheduler(bot, config)
    log.info("Бот «Дарвин» запущен (поллинг).")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Остановка по Ctrl+C.")


if __name__ == "__main__":
    main()
