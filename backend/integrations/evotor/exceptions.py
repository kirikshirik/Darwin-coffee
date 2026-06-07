"""Исключения интеграции с Эвотором.

Делим на три типа, чтобы вызывающий код мог по-разному реагировать:
  • EvotorConfigError — нет токена/конфига (чиним до запуска, это наш блокер).
  • EvotorAuthError   — 401/403 от Облака (токен не тот / нет прав / не тот заголовок).
  • EvotorAPIError    — прочие ошибки HTTP/сети (можно ретраить).
"""
from __future__ import annotations


class EvotorError(Exception):
    """Базовая ошибка интеграции с Эвотором."""


class EvotorConfigError(EvotorError):
    """Не задан Cloud Token или другой обязательный параметр конфигурации."""


class EvotorAuthError(EvotorError):
    """Облако Эвотор отклонило авторизацию (401/403).

    Самая вероятная причина на старте — не тот заголовок/формат токена.
    Cloud Token идёт в `X-Authorization` СЫРЫМ (без `Bearer`), OAuth-токен —
    в `Authorization: Bearer ...`. См. EvotorConfig.auth_header.
    """


class EvotorAPIError(EvotorError):
    """Ошибка ответа Облака (не 2xx) или сети.

    Хранит HTTP-статус и тело ответа — пригодится при разборе первых реальных
    запросов (понять, какие поля и ошибки реально приходят).
    """

    def __init__(self, message: str, *, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body
