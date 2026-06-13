"""EvotorClient — асинхронный клиент REST API Облака Эвотор.

Эндпоинты и авторизация СВЕРЕНЫ с официальной докой (developer.evotor.ru),
а не взяты из брейншторма `info` (там пути были выдуманы — блокер №2 снят):

    Авторизация : заголовок `X-Authorization: <cloud_token>` (СЫРОЙ, без «Bearer»)
    Версия API  : через media-type  `Accept: application/vnd.evotor.v2+json`
    Base URL    : https://api.evotor.ru
    Магазины    : GET /stores
    Товары      : GET /stores/{store-id}/products      (пагинация: cursor → paging.next_cursor)
    Документы   : GET /stores/{store-id}/documents      (since/until в мс, type=SELL,…, cursor)

Документ продажи: type="SELL", close_date (ISO 8601, TZ +0000), body.positions[]
(product_name, quantity, price, result_sum), body.result_sum, body.payments[] (type, sum).

Что НЕЛЬЗЯ узнать без реального токена (проверить на первых ~100 чеках):
  • в каких единицах деньги (рубли или копейки) — см. mapping.MONEY_IN_KOPECKS;
  • точные имена части полей и доступность метода на тарифе кофейни;
  • совпадает ли заголовок (X-Authorization vs OAuth Bearer) для этого аккаунта.
Поэтому имена заголовков/версия вынесены в EvotorConfig (можно переопределить через .env).

Запуск без токена (offline, на образцах ответа): backend.integrations.evotor.demo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from .config import EvotorConfig
from .exceptions import EvotorAPIError, EvotorAuthError

# Типы документов Эвотора, которые нас интересуют для аналитики продаж.
DOC_SELL = "SELL"
DOC_PAYBACK = "PAYBACK"


def _to_millis(dt: datetime) -> int:
    """datetime → Unix-время в миллисекундах (наивный datetime считаем UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


class EvotorClient:
    """Тонкая обёртка над REST API Эвотора. Деньги/маппинг — в mapping.py.

    Использование::

        async with EvotorClient.from_env() as evotor:
            stores = await evotor.get_stores()
            sells = await evotor.get_documents(store_id, since, until)
    """

    def __init__(self, config: EvotorConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_env(cls) -> "EvotorClient":
        """Собрать клиент из переменных окружения (.env). Бросит EvotorConfigError без токена."""
        return cls(EvotorConfig.from_env())

    # --- управление HTTP-сессией -------------------------------------------------
    @property
    def headers(self) -> dict[str, str]:
        return {
            self.config.auth_header: self.config.auth_value,
            "Accept": self.config.media_type,
            "Content-Type": self.config.media_type,
        }

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=self.headers,
                timeout=self.config.timeout,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "EvotorClient":
        self._ensure_client()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # --- низкоуровневый GET ------------------------------------------------------
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        client = self._ensure_client()
        try:
            resp = await client.get(path, params=params)
        except httpx.HTTPError as e:  # сетевые/таймаут — ретраибельно
            raise EvotorAPIError(f"Сетевая ошибка при GET {path}: {e}") from e

        if resp.status_code in (401, 403):
            raise EvotorAuthError(
                f"Облако Эвотор отклонило запрос ({resp.status_code}). Проверь Cloud Token "
                f"и заголовок авторизации ({self.config.auth_header}). Тело: {resp.text[:300]}"
            )
        if resp.status_code >= 400:
            raise EvotorAPIError(
                f"Ошибка Эвотора {resp.status_code} на GET {path}",
                status=resp.status_code,
                body=resp.text[:1000],
            )
        try:
            return resp.json()
        except ValueError as e:
            raise EvotorAPIError(f"Ответ Эвотора на {path} — не JSON: {resp.text[:300]}") from e

    async def _paginate(
        self, path: str, params: dict[str, Any] | None = None
    ) -> AsyncIterator[dict]:
        """Идём по страницам, пока есть курсор. Курсор лежит в paging.next_cursor.

        Поддерживаем и плоский next_cursor — на случай различий между методами.
        """
        params = dict(params or {})
        seen_cursors: set[str] = set()
        while True:
            data = await self._get(path, params)
            for item in data.get("items", []):
                yield item
            cursor = (data.get("paging") or {}).get("next_cursor") or data.get("next_cursor")
            if not cursor or cursor in seen_cursors:
                break
            seen_cursors.add(cursor)
            params["cursor"] = cursor

    # --- публичные методы --------------------------------------------------------
    async def get_stores(self) -> list[dict]:
        """Список магазинов аккаунта. GET /stores."""
        data = await self._get("/stores")
        return data.get("items", [])

    async def get_products(self, store_id: str) -> list[dict]:
        """Каталог товаров магазина (все страницы). GET /stores/{id}/products."""
        return [p async for p in self._paginate(f"/stores/{store_id}/products")]

    async def get_employees(self) -> list[dict]:
        """Сотрудники аккаунта (все страницы). GET /employees.

        Поля item: id (UUID сотрудника), name/last_name/patronymic_name, role
        (ADMIN/CASHIER/…), stores[]. Кассир чека — close_user_id документа,
        совпадает с id сотрудника (сверено с докой и живыми данными).
        """
        return [e async for e in self._paginate("/employees")]

    async def get_documents(
        self,
        store_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        types: tuple[str, ...] = (DOC_SELL,),
    ) -> list[dict]:
        """Документы магазина за период (все страницы). GET /stores/{id}/documents.

        since/until — границы периода (наивный datetime трактуется как UTC), в API
        уходят как Unix-мс. types — фильтр по типу документа (по умолчанию только продажи).
        """
        params: dict[str, Any] = {}
        if since is not None:
            params["since"] = _to_millis(since)
        if until is not None:
            params["until"] = _to_millis(until)
        if types:
            params["type"] = ",".join(types)
        return [d async for d in self._paginate(f"/stores/{store_id}/documents", params)]

    async def get_sales(
        self, store_id: str, since: datetime, until: datetime
    ) -> list[dict]:
        """Только чеки продаж (type=SELL) за период — самый частый запрос аналитики."""
        return await self.get_documents(store_id, since, until, types=(DOC_SELL,))
