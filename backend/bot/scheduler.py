"""Планировщик ежедневной утренней сводки (APScheduler + aiogram).

Каждое утро в TELEGRAM_REPORT_TIME (TZ из конфига) считает отчёт за вчера и шлёт
его владельцу (TELEGRAM_OWNER_CHAT_ID). Время/таймзона — в .env.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.bot import reports
from backend.bot.config import BotConfig

log = logging.getLogger(__name__)


async def send_morning_report(bot: Bot, chat_id: int) -> None:
    text = reports.morning_text()
    await bot.send_message(chat_id, text)
    log.info("Утренняя сводка отправлена в чат %s", chat_id)


def setup_scheduler(bot: Bot, config: BotConfig) -> AsyncIOScheduler:
    """Создать и запустить планировщик утренних отчётов.

    Если TELEGRAM_OWNER_CHAT_ID не задан — джоба не ставится (некуда слать),
    бот работает только по кнопкам. Узнать chat_id: написать боту /start и
    посмотреть update, либо через @userinfobot.
    """
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    if config.owner_chat_id is None:
        log.warning(
            "TELEGRAM_OWNER_CHAT_ID не задан — утренняя рассылка выключена "
            "(бот отвечает только на кнопки)."
        )
        scheduler.start()
        return scheduler

    hh, mm = config.report_hh_mm
    scheduler.add_job(
        send_morning_report,
        trigger=CronTrigger(hour=hh, minute=mm, timezone=config.timezone),
        args=(bot, config.owner_chat_id),
        id="morning_report",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    log.info("Планировщик запущен: сводка ежедневно в %02d:%02d (%s)", hh, mm, config.timezone)
    return scheduler
