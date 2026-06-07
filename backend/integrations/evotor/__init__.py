"""Интеграция с Облаком Эвотор.

Публичный API пакета::

    from backend.integrations.evotor import EvotorClient, EvotorConfig
    from backend.integrations.evotor import mapping

Эндпоинты и авторизация сверены с developer.evotor.ru (см. client.py).
Без Cloud Token (блокер №1) работает offline-демо: backend.integrations.evotor.demo.
"""
from __future__ import annotations

from .client import EvotorClient
from .config import EvotorConfig
from .exceptions import (
    EvotorAPIError,
    EvotorAuthError,
    EvotorConfigError,
    EvotorError,
)

__all__ = [
    "EvotorClient",
    "EvotorConfig",
    "EvotorError",
    "EvotorConfigError",
    "EvotorAuthError",
    "EvotorAPIError",
]
