"""Маппинг ответов Эвотора → доменные модели (Product / Receipt / ReceiptItem).

Чистые функции (dict → объект) + апсерт в БД. Сетевого кода здесь нет — поэтому
маппинг тестируется offline на sample_data, без токена и без httpx (demo.py).

Деньги — только Decimal (см. CLAUDE.md / ARCHITECTURE). Себестоимость позиции
Эвотор НЕ отдаёт (подтверждено докой: в /products нет cost_price), поэтому cost
берём из нашего справочника `cost_reference` по имени товара, а не из Эвотора.

⚠️ ПРОВЕРИТЬ НА ПЕРВЫХ РЕАЛЬНЫХ ЧЕКАХ (это и есть смысл Фазы 1):
  • MONEY_IN_KOPECKS — в каких единицах приходят price/result_sum (рубли или копейки).
    Дока единицы не фиксирует; на образцах считаем, что РУБЛИ. Если в реале копейки —
    переключить флаг (или env EVOTOR_MONEY_IN_KOPECKS=1) и сверить итог с Эвотором.
  • Точные имена полей позиции (product_name/quantity/price/result_sum) — взяты из доки,
    но первые ответы могут отличаться по тарифу; _money/_get_any это переживут.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Product, Receipt, ReceiptItem

# Деньги Эвотора: на образцах — рубли. Переопределяется через окружение.
MONEY_IN_KOPECKS = os.getenv("EVOTOR_MONEY_IN_KOPECKS", "0").strip() in ("1", "true", "True")

CENT = Decimal("0.01")
QTY = Decimal("0.001")
ZERO = Decimal("0")

# Эвотор отдаёт close_date в UTC (+0000), а колонка sold_at наивная и запросы бота
# наивные. Приводим время к локальной TZ кофейни и убираем tzinfo — иначе ломается
# сравнение naive/aware в SQLite и «прибыльные часы» съезжают на смещение UTC.
LOCAL_TZ = ZoneInfo(os.getenv("EVOTOR_TZ", "Europe/Moscow"))


def _money(value: object) -> Decimal:
    """Любое число Эвотора → Decimal в рублях (с учётом MONEY_IN_KOPECKS)."""
    if value is None:
        return ZERO
    amount = Decimal(str(value))
    if MONEY_IN_KOPECKS:
        amount = amount / Decimal("100")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _qty(value: object) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(QTY, rounding=ROUND_HALF_UP)


def _get_any(d: Mapping, *keys: str, default=None):
    """Вернуть первое присутствующее поле (страхуемся от разнобоя имён в ответе)."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _parse_dt(value: object) -> datetime:
    """close_date Эвотора (ISO 8601, TZ +0000) → НАИВНЫЙ datetime в локальной TZ кофейни.

    Z и +0000 поддержаны. Если время пришло с таймзоной — переводим в LOCAL_TZ и
    срезаем tzinfo (см. комментарий к LOCAL_TZ). Наивное время оставляем как есть.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip().replace("Z", "+00:00")
        # Эвотор отдаёт смещение как +0000 (без двоеточия) — Python 3.9 fromisoformat
        # его не понимает и падает в запасной разбор, теряя TZ. Нормализуем → +00:00.
        s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            dt = datetime.fromisoformat(s[:19])  # запасной разбор без TZ
    if dt.tzinfo is not None:
        dt = dt.astimezone(LOCAL_TZ).replace(tzinfo=None)
    return dt


def is_sale(doc: Mapping) -> bool:
    return _get_any(doc, "type", default="") == "SELL"


# --- маппинг отдельных сущностей --------------------------------------------------
def map_product(raw: Mapping, business_id: int) -> Product:
    """Товар Эвотора → Product. cost_price не из Эвотора (его там нет) → 0, ведём сами."""
    return Product(
        business_id=business_id,
        evotor_uuid=_get_any(raw, "id", "uuid"),
        name=_get_any(raw, "name", default="(без названия)"),
        category=_get_any(raw, "parent_id", "category"),
        sell_price=_money(_get_any(raw, "price", default=0)),
        cost_price=ZERO,  # Эвотор не хранит себестоимость; см. cost_reference
        active=not bool(_get_any(raw, "is_removed", "isRemoved", default=False)),
    )


def map_receipt(
    raw: Mapping,
    business_id: int,
    cost_by_name: Optional[Mapping[str, Decimal]] = None,
    product_id_by_name: Optional[Mapping[str, int]] = None,
) -> Optional[Receipt]:
    """Документ продажи (SELL) → Receipt с позициями. Не-продажи → None.

    cost_by_name — справочник «имя товара → себестоимость порции» (из cost_reference);
    если по позиции нет себестоимости, cost=0 (маржу по ней не считаем, но выручку — да).
    product_id_by_name — «имя товара → Product.id» для связи позиции с товаром (нужно
    для топа товаров); позиция Эвотора несёт только имя, поэтому связываем по имени.
    """
    if not is_sale(raw):
        return None

    body = _get_any(raw, "body", default={}) or {}
    cost_by_name = cost_by_name or {}
    product_id_by_name = product_id_by_name or {}

    total = _money(_get_any(body, "result_sum", default=_get_any(raw, "result_sum", default=0)))
    payments = _get_any(body, "payments", default=[]) or []
    payment_type = payments[0].get("type") if payments else None

    receipt = Receipt(
        business_id=business_id,
        receipt_uuid=_get_any(raw, "id", "uuid"),
        sold_at=_parse_dt(_get_any(raw, "close_date", "date", default=datetime.utcnow().isoformat())),
        total_sum=total,
        payment_type=payment_type,
        # user_id Эвотора = сотрудник, оформивший чек (UUID; имя резолвится позже).
        cashier=_get_any(raw, "user_id", default=_get_any(body, "user_id")),
    )

    for pos in _get_any(body, "positions", default=[]) or []:
        name = _get_any(pos, "product_name", "name", default="(позиция)")
        qty = _qty(_get_any(pos, "quantity", "qty", default=0))
        price = _money(_get_any(pos, "price", default=0))
        revenue = _money(_get_any(pos, "result_sum", "result", default=qty * price))
        cost = (cost_by_name.get(name, ZERO) * qty).quantize(CENT, rounding=ROUND_HALF_UP)
        receipt.items.append(
            ReceiptItem(
                product_id=product_id_by_name.get(name),
                quantity=qty,
                price=price,
                revenue=revenue,
                cost=cost,
                profit=(revenue - cost),
            )
        )
    return receipt


# --- апсерт в БД ------------------------------------------------------------------
def sync_products(session: Session, business_id: int, raw_products: Iterable[Mapping]) -> int:
    """Идемпотентно записать товары: обновить по evotor_uuid или создать новый."""
    existing = {
        p.evotor_uuid: p
        for p in session.scalars(
            select(Product).where(Product.business_id == business_id)
        )
        if p.evotor_uuid
    }
    n = 0
    for raw in raw_products:
        mapped = map_product(raw, business_id)
        cur = existing.get(mapped.evotor_uuid)
        if cur is None:
            session.add(mapped)
        else:
            cur.name = mapped.name
            cur.category = mapped.category
            cur.sell_price = mapped.sell_price
            cur.active = mapped.active
        n += 1
    session.commit()
    return n


def sync_sales(
    session: Session,
    business_id: int,
    raw_documents: Iterable[Mapping],
    cost_by_name: Optional[Mapping[str, Decimal]] = None,
) -> int:
    """Записать чеки продаж. Дубли по receipt_uuid пропускаем (идемпотентно).

    Перед загрузкой чеков стоит вызвать sync_products: тогда позиции свяжутся с
    товарами по имени (product_id), а себестоимость возьмётся из product.cost_price,
    если явный cost_by_name не передан.
    """
    products = list(
        session.scalars(select(Product).where(Product.business_id == business_id))
    )
    product_id_by_name = {p.name: p.id for p in products if p.id is not None}
    if cost_by_name is None:
        cost_by_name = {p.name: p.cost_price for p in products if p.cost_price}

    seen = {
        r
        for r in session.scalars(
            select(Receipt.receipt_uuid).where(Receipt.business_id == business_id)
        )
        if r
    }
    added = 0
    for raw in raw_documents:
        receipt = map_receipt(raw, business_id, cost_by_name, product_id_by_name)
        if receipt is None or receipt.receipt_uuid in seen:
            continue
        session.add(receipt)
        seen.add(receipt.receipt_uuid)
        added += 1
    session.commit()
    return added
