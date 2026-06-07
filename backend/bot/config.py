"""Конфигурация Telegram-бота (из переменных окружения / .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_TZ = "Europe/Moscow"
DEFAULT_REPORT_TIME = "09:00"  # во сколько слать утреннюю сводку (локальное время TZ)


class BotConfigError(RuntimeError):
    """Не задан токен бота или чат владельца."""


@dataclass(frozen=True)
class BotConfig:
    token: str
    owner_chat_id: int | None
    timezone: str = DEFAULT_TZ
    report_time: str = DEFAULT_REPORT_TIME

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise BotConfigError(
                "TELEGRAM_BOT_TOKEN не задан. Создай бота у @BotFather, положи токен в .env "
                "(см. .env.example). Без него поллинг не стартует; логику отчётов можно "
                "проверить без токена: .venv/bin/python -m backend.bot.demo"
            )
        chat = os.getenv("TELEGRAM_OWNER_CHAT_ID", "").strip()
        return cls(
            token=token,
            owner_chat_id=int(chat) if chat else None,
            timezone=os.getenv("TELEGRAM_TZ", DEFAULT_TZ),
            report_time=os.getenv("TELEGRAM_REPORT_TIME", DEFAULT_REPORT_TIME),
        )

    @property
    def report_hh_mm(self) -> tuple[int, int]:
        hh, mm = self.report_time.split(":")
        return int(hh), int(mm)
