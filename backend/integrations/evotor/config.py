"""Конфигурация доступа к Облаку Эвотор (из переменных окружения / .env).

Все значения, КРОМЕ токена, имеют разумные значения по умолчанию, сверенные с
официальной докой https://developer.evotor.ru (см. шапку client.py). Токена нет —
это блокер №1 проекта; до его получения интеграцию можно гонять только на
sample_data (offline), что и делает demo.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .exceptions import EvotorConfigError

load_dotenv()  # подхватываем .env, если он есть (см. .env.example)

# Значения по умолчанию — сверены с официальной докой Эвотора.
DEFAULT_BASE_URL = "https://api.evotor.ru"
# Cloud Token идёт СЫРЫМ в заголовке X-Authorization (НЕ "Bearer").
# Для OAuth-доступа поменять на EVOTOR_AUTH_HEADER=Authorization и EVOTOR_AUTH_SCHEME=Bearer.
DEFAULT_AUTH_HEADER = "X-Authorization"
DEFAULT_AUTH_SCHEME = ""  # пусто = токен передаётся как есть, без префикса
# Версионирование API задаётся media-type'ом (Accept), а не путём.
DEFAULT_MEDIA_TYPE = "application/vnd.evotor.v2+json"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class EvotorConfig:
    token: str
    base_url: str = DEFAULT_BASE_URL
    auth_header: str = DEFAULT_AUTH_HEADER
    auth_scheme: str = DEFAULT_AUTH_SCHEME
    media_type: str = DEFAULT_MEDIA_TYPE
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_env(cls) -> "EvotorConfig":
        token = os.getenv("EVOTOR_CLOUD_TOKEN", "").strip()
        if not token:
            raise EvotorConfigError(
                "EVOTOR_CLOUD_TOKEN не задан. Это блокер №1: без облачного токена "
                "аккаунта «Дарвина» Облако Эвотор недоступно. Получить токен в личном "
                "кабинете Эвотора, положить в .env (см. .env.example). Пока токена нет — "
                "интеграцию можно проверять только на sample_data: "
                "`.venv/bin/python -m backend.integrations.evotor.demo`."
            )
        return cls(
            token=token,
            base_url=os.getenv("EVOTOR_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            auth_header=os.getenv("EVOTOR_AUTH_HEADER", DEFAULT_AUTH_HEADER),
            auth_scheme=os.getenv("EVOTOR_AUTH_SCHEME", DEFAULT_AUTH_SCHEME),
            media_type=os.getenv("EVOTOR_MEDIA_TYPE", DEFAULT_MEDIA_TYPE),
            timeout=float(os.getenv("EVOTOR_TIMEOUT", str(DEFAULT_TIMEOUT))),
        )

    @property
    def auth_value(self) -> str:
        """Значение заголовка авторизации: '<scheme> <token>' или просто '<token>'."""
        return f"{self.auth_scheme} {self.token}".strip()
