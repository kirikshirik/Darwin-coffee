"""Планировщик фоновых задач бота (APScheduler + aiogram).

1. Утренняя сводка — каждое утро в TELEGRAM_REPORT_TIME (TZ из конфига): отчёт за
   вчера владельцу (TELEGRAM_OWNER_CHAT_ID).
2. Синк Эвотора — если задан EVOTOR_SYNC_INTERVAL_MIN (>0) и есть EVOTOR_CLOUD_TOKEN:
   тянет чеки/товары в БД каждые N минут прямо в процессе бота. Нужно там, где нет
   отдельного systemd-таймера (например, на Render/PaaS). На VPS интервал не задаётся —
   синк делает darwin-sync.timer.

Время/таймзона/интервал — в .env.
"""
from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.bot import reports
from backend.bot.config import BotConfig
from backend.integrations.evotor import sync as evotor_sync

log = logging.getLogger(__name__)

SYNC_DAYS = 3  # окно инкрементального синка (как у darwin-sync.service)


async def send_morning_report(bot: Bot, chat_ids: tuple[int, ...]) -> None:
    """Утренняя сводка всем владельцам. Текст считаем один раз; сбой одному не мешает другим."""
    text = reports.morning_text()
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
            log.info("Утренняя сводка отправлена в чат %s", chat_id)
        except Exception:
            log.exception("Не удалось отправить сводку в чат %s", chat_id)


async def run_evotor_sync() -> None:
    """Плановый синк Эвотор → БД. Блокирующий sync() уводим в поток; ошибки только логируем."""
    try:
        await asyncio.to_thread(evotor_sync.sync, SYNC_DAYS)
        log.info("Плановый синк Эвотора выполнен")
    except Exception:
        log.exception("Плановый синк Эвотора не прошёл")


def _sync_interval_min() -> int:
    """EVOTOR_SYNC_INTERVAL_MIN из .env. 0/пусто/мусор → синк в процессе выключен."""
    try:
        return max(0, int(os.getenv("EVOTOR_SYNC_INTERVAL_MIN", "0")))
    except ValueError:
        return 0


def setup_scheduler(bot: Bot, config: BotConfig) -> AsyncIOScheduler:
    """Создать и запустить планировщик утренних отчётов.

    Если TELEGRAM_OWNER_CHAT_ID не задан — джоба не ставится (некуда слать),
    бот работает только по кнопкам. Узнать chat_id: написать боту /start и
    посмотреть update, либо через @userinfobot.
    """
    scheduler = AsyncIOScheduler(timezone=config.timezone)

    # 1) Утренняя сводка — только если задан хотя бы один владелец.
    if not config.owner_chat_ids:
        log.warning(
            "TELEGRAM_OWNER_CHAT_ID не задан — утренняя рассылка выключена "
            "(бот отвечает только на кнопки)."
        )
    else:
        hh, mm = config.report_hh_mm
        scheduler.add_job(
            send_morning_report,
            trigger=CronTrigger(hour=hh, minute=mm, timezone=config.timezone),
            args=(bot, config.owner_chat_ids),
            id="morning_report",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        log.info(
            "Сводка по расписанию: ежедневно в %02d:%02d (%s) — владельцев: %d",
            hh, mm, config.timezone, len(config.owner_chat_ids),
        )

    # 2) Синк Эвотора в процессе — только если задан интервал И есть токен.
    interval = _sync_interval_min()
    has_token = bool(os.getenv("EVOTOR_CLOUD_TOKEN", "").strip())
    if interval and has_token:
        scheduler.add_job(
            run_evotor_sync,
            trigger=IntervalTrigger(minutes=interval),
            id="evotor_sync",
            replace_existing=True,
            misfire_grace_time=interval * 60,
            max_instances=1,  # не накладывать синки, если предыдущий ещё идёт
            coalesce=True,
        )
        log.info("Синк Эвотора по расписанию: каждые %d мин (в процессе бота)", interval)
    elif interval and not has_token:
        log.warning("EVOTOR_SYNC_INTERVAL_MIN задан, но EVOTOR_CLOUD_TOKEN пуст — синк не ставлю.")

    scheduler.start()
    return scheduler
