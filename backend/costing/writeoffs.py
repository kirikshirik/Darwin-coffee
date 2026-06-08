"""Управление потерями (списание) — перевод физических потерь в деньги.

Каждое списание — это реальные деньги, которые сейчас нигде не видны: пролитый
при настройке помола эспрессо, скисшее молоко, бой посуды, просрочка выпечки.
Стоимость потери считается из того же справочника закупочных цен, что и тех-карты
(`ingredients.price_book`), поэтому при удорожании сырья растёт и цена списаний.

Зачем это продукту: списания — скрытая часть COGS. Подняв их, мы показываем
владельцу честную картину («на калибровке помола вы за месяц вылили зерна на N ₽»)
и даём этим потерям статью, которой в Excel нет. Стыкуется с тезисом honest-P&L.

Каркас: модель списания + оценка типовых потерь + сводка по причинам/ингредиентам
и доля в выручке/COGS. Реальные объёмы (сколько шотов в день уходит на калибровку,
сколько молока скисает) вносит владелец или мы поднимаем из учёта — пока это вход.

Деньги — только Decimal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D, ROUND_HALF_UP
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional

from backend.costing import ingredients as ing

ZERO = D("0")


def _r2(x: D) -> D:
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


class WriteOffReason(str, Enum):
    """Причины списания — для группировки в сводке и адресных рекомендаций."""

    CALIBRATION = "Настройка помола (пролив эспрессо)"
    SOURED_MILK = "Скисшее молоко"
    EXPIRED = "Просрочка (выпечка, продукты)"
    BREAKAGE = "Бой посуды / упаковки"
    TRAINING = "Обучение бариста"
    OTHER = "Прочие потери"


@dataclass(frozen=True)
class WriteOff:
    """Факт списания: сколько и какого ингредиента потеряно и почему.

    `quantity` — в базовой единице ингредиента (г зерна, мл молока, шт стакана).
    `period` — первое число месяца, как у Expense (потери ведём помесячно).
    """

    period: date
    ingredient: str
    quantity: D
    reason: WriteOffReason
    comment: str = ""

    def cost(self, prices: Mapping[str, D] | None = None) -> D:
        """Денежная оценка потери по текущему (или переданному) прайсу, ₽."""
        book = prices if prices is not None else ing.price_book()
        if self.ingredient not in book:
            raise KeyError(f"Нет цены для «{self.ingredient}» в прайсе")
        return _r2(self.quantity * book[self.ingredient])


# --- Оценка типовых потерь (помогает владельцу прикинуть, пока нет точного учёта) ---

# Расход зерна на одну порцию эспрессо — из тех-карты (17 г), для оценки калибровки.
ESPRESSO_DOSE_G = D("17")


def estimate_calibration(
    period: date,
    shots_per_day: D,
    days: int = 30,
    dose_g: D = ESPRESSO_DOSE_G,
) -> WriteOff:
    """Списание зерна на настройку помола: N проливов/день × доза × дни.

    Пример: 4 пробных шота в день × 17 г × 30 дней = 2040 г зерна в потери.
    """
    qty = D(shots_per_day) * D(dose_g) * D(days)
    return WriteOff(
        period=period,
        ingredient="зерно",
        quantity=qty,
        reason=WriteOffReason.CALIBRATION,
        comment=f"{shots_per_day} шот/день × {dose_g} г × {days} дн",
    )


def estimate_soured_milk(
    period: date,
    liters: D,
) -> WriteOff:
    """Списание скисшего/непроданного молока за период (в литрах → мл)."""
    return WriteOff(
        period=period,
        ingredient="молоко",
        quantity=D(liters) * D("1000"),
        reason=WriteOffReason.SOURED_MILK,
        comment=f"{liters} л скисшего/просроченного молока",
    )


# --- Сводка ---------------------------------------------------------------

@dataclass
class WriteOffSummary:
    total: D
    by_reason: Dict[WriteOffReason, D]
    by_ingredient: Dict[str, D]
    share_of_revenue_pct: Optional[float]
    share_of_cogs_pct: Optional[float]


def summarize(
    writeoffs: Iterable[WriteOff],
    prices: Mapping[str, D] | None = None,
    revenue: Optional[D] = None,
    cogs: Optional[D] = None,
) -> WriteOffSummary:
    """Итог потерь: всего, по причинам, по ингредиентам и доля в выручке/COGS.

    `revenue`/`cogs` опциональны — если переданы, считаем, какую долю потери
    «съедают» (то, что сейчас невидимо в P&L). Это и есть ценность для владельца.
    """
    book = prices if prices is not None else ing.price_book()
    by_reason: Dict[WriteOffReason, D] = {}
    by_ingredient: Dict[str, D] = {}
    total = ZERO
    for w in writeoffs:
        c = w.cost(book)
        total += c
        by_reason[w.reason] = by_reason.get(w.reason, ZERO) + c
        by_ingredient[w.ingredient] = by_ingredient.get(w.ingredient, ZERO) + c

    def _share(part: D, whole: Optional[D]) -> Optional[float]:
        if not whole:
            return None
        return float((part / whole * 100).quantize(D("0.1"), rounding=ROUND_HALF_UP))

    return WriteOffSummary(
        total=_r2(total),
        by_reason={k: _r2(v) for k, v in by_reason.items()},
        by_ingredient={k: _r2(v) for k, v in by_ingredient.items()},
        share_of_revenue_pct=_share(total, revenue),
        share_of_cogs_pct=_share(total, cogs),
    )
