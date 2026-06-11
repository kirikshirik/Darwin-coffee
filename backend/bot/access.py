"""Контроль доступа к боту: пускать только владельцев.

Бот «Дарвин» показывает финансы (выручка, прибыль, P&L), поэтому отвечать должен
только владельцам из TELEGRAM_OWNER_CHAT_ID. Реализовано одним message-middleware,
который покрывает ВСЕ хендлеры (кнопки, /start, /dashboard) в одном месте.

Если список владельцев пуст (бот не настроен) — пропускаем всех, чтобы не «закирпичить»
инстанс; на проде список задан, поэтому доступ закрыт.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

log = logging.getLogger(__name__)


class OwnerOnlyMiddleware(BaseMiddleware):
    """Пропускать сообщения только от владельцев; остальным — вежливый отказ."""

    def __init__(self, owner_ids: tuple[int, ...]) -> None:
        self.owner_ids = set(owner_ids)
        if not self.owner_ids:
            log.warning("Список владельцев пуст — доступ к боту НЕ ограничен (открыт всем).")

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if self.owner_ids and event.chat.id not in self.owner_ids:
            log.info("Отказано в доступе чату %s (не владелец)", event.chat.id)
            await event.answer("Доступ только для владельцев бота.")
            return None  # дальше в хендлер не пускаем
        return await handler(event, data)
