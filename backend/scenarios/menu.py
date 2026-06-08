"""Калькулятор LTV, среднего чека и маржинальности меню.

Отвечает на вопрос владельца: «как добавление в меню выпечки или сиропов влияет
на средний чек и маржинальность?». Берёт меню (позиция = цена продажи + себестоимость
+ объём продаж) и считает выручку, средний чек, маржу. Затем моделирует ввод новой
позиции или допа-апсейла и показывает Δ среднего чека и Δ маржи.

Себестоимость берём из тех-карт (`backend.costing.techcard`), цену продажи — от
владельца (её Эвотор не отдаёт). Пока цен продажи нет, модуль принимает их как вход
и честно помечает позиции без цены/себестоимости предупреждениями (как ProfitCalculator).

LTV — простая прозрачная формула со ВХОДНЫМИ допущениями (частота визитов и горизонт
удержания у нас пока нет данных → владелец задаёт; см. предупреждения).

Деньги — только Decimal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal as D, ROUND_HALF_UP
from typing import List, Optional

ZERO = D("0")


def _r2(x: D) -> D:
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _pct(part: D, whole: D) -> float:
    if not whole:
        return 0.0
    return float((part / whole * 100).quantize(D("0.1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class MenuItem:
    """Позиция меню: цена продажи и себестоимость (из тех-карты)."""

    name: str
    sell_price: D
    cost: D
    category: str = ""

    @property
    def margin(self) -> D:
        return _r2(D(self.sell_price) - D(self.cost))

    @property
    def margin_pct(self) -> float:
        return _pct(D(self.sell_price) - D(self.cost), D(self.sell_price))


@dataclass(frozen=True)
class MenuLine:
    """Позиция + сколько продано за период (структура продаж / sales mix)."""

    item: MenuItem
    units: D


@dataclass
class MenuMetrics:
    revenue: D
    cost: D
    profit: D
    units: D
    avg_item_price: D     # выручка / число проданных позиций
    margin_pct: float
    warnings: List[str] = field(default_factory=list)


class Menu:
    """Меню как структура продаж: позиции и их объёмы за период."""

    def __init__(self, lines: Optional[List[MenuLine]] = None):
        self.lines: List[MenuLine] = list(lines or [])

    def add(self, item: MenuItem, units: D) -> "Menu":
        return Menu(self.lines + [MenuLine(item, D(units))])

    def metrics(self) -> MenuMetrics:
        revenue = sum((l.item.sell_price * l.units for l in self.lines), ZERO)
        cost = sum((l.item.cost * l.units for l in self.lines), ZERO)
        units = sum((l.units for l in self.lines), ZERO)
        profit = revenue - cost
        m = MenuMetrics(
            revenue=_r2(revenue),
            cost=_r2(cost),
            profit=_r2(profit),
            units=units,
            avg_item_price=_r2(revenue / units) if units else ZERO,
            margin_pct=_pct(profit, revenue),
        )
        m.warnings = self._check(m)
        return m

    def avg_check(self, checks_count: int) -> D:
        """Истинный средний чек = выручка / число чеков (если известно число чеков)."""
        if not checks_count:
            return ZERO
        return _r2(self.metrics().revenue / D(checks_count))

    def _check(self, m: MenuMetrics) -> List[str]:
        warns: List[str] = []
        no_price = [l.item.name for l in self.lines if not l.item.sell_price]
        if no_price:
            warns.append(
                "Нет цены продажи у позиций: " + ", ".join(no_price) +
                " — нужны от владельца для честной маржи."
            )
        no_cost = [l.item.name for l in self.lines if not l.item.cost]
        if no_cost:
            warns.append(
                "Нет себестоимости у позиций: " + ", ".join(no_cost) +
                " — привязать тех-карту (backend.costing.techcard)."
            )
        return warns


# --- Моделирование изменений меню ----------------------------------------
#
# Главная метрика — средний ЧЕК (выручка / число чеков), а не цена позиции:
# именно про чек спрашивает владелец. Поэтому импакт считается при заданном
# числе чеков. Доп-апсейл число чеков не меняет (доливается в текущие) → чек растёт;
# новая позиция может приносить и собственные новые чеки (`new_checks`).

@dataclass
class MenuImpact:
    """Эффект изменения меню: было/стало по среднему чеку и марже + дельты."""

    avg_check_before: D
    avg_check_after: D
    avg_check_delta: D
    margin_pct_before: float
    margin_pct_after: float
    margin_pct_delta: float
    profit_before: D
    profit_after: D
    profit_delta: D


def _impact(
    before: MenuMetrics, after: MenuMetrics, checks_before: D, checks_after: D
) -> MenuImpact:
    ac_before = _r2(before.revenue / checks_before) if checks_before else ZERO
    ac_after = _r2(after.revenue / checks_after) if checks_after else ZERO
    return MenuImpact(
        avg_check_before=ac_before,
        avg_check_after=ac_after,
        avg_check_delta=_r2(ac_after - ac_before),
        margin_pct_before=before.margin_pct,
        margin_pct_after=after.margin_pct,
        margin_pct_delta=round(after.margin_pct - before.margin_pct, 1),
        profit_before=before.profit,
        profit_after=after.profit,
        profit_delta=_r2(after.profit - before.profit),
    )


def impact_of_new_item(
    menu: Menu, item: MenuItem, units: D, checks_count: D, new_checks: D = ZERO
) -> MenuImpact:
    """Эффект ввода новой позиции (например, выпечки) с прогнозом объёма продаж.

    `new_checks` — сколько ИЗ `units` приходят отдельными новыми чеками (новый повод
    зайти); остальное добирается к текущим чекам. По умолчанию все добираются.
    """
    return _impact(
        menu.metrics(),
        menu.add(item, units).metrics(),
        D(checks_count),
        D(checks_count) + D(new_checks),
    )


def impact_of_addon(
    menu: Menu, addon: MenuItem, attach_rate: D, checks_count: D
) -> MenuImpact:
    """Эффект допа-апсейла (сироп), который берут к `attach_rate` доли текущих позиций.

    `attach_rate` ∈ [0..1]: 0.30 = сироп добавляют к 30% проданных напитков.
    Доп не создаёт новый чек, а доливает выручку/себестоимость к текущим →
    число чеков неизменно, средний чек растёт.
    """
    before = menu.metrics()
    attached_units = before.units * D(attach_rate)
    after = menu.add(addon, attached_units).metrics()
    return _impact(before, after, D(checks_count), D(checks_count))


# --- LTV ------------------------------------------------------------------

@dataclass
class LTV:
    value: D
    avg_check: D
    visits_per_month: D
    lifespan_months: D
    margin_pct: float
    warnings: List[str] = field(default_factory=list)


def ltv(
    avg_check: D,
    visits_per_month: D,
    lifespan_months: D,
    margin_pct: float,
) -> LTV:
    """LTV = средний чек × визитов/мес × горизонт (мес) × маржа.

    Прозрачная маржинальная LTV: сколько чистой прибыли принесёт клиент за срок
    удержания. Частоту визитов и горизонт удержания у нас пока нет в данных —
    это ВХОД от владельца / будущая когортная аналитика по чекам Эвотора.
    """
    margin = D(str(margin_pct)) / D("100")
    value = D(avg_check) * D(visits_per_month) * D(lifespan_months) * margin
    warns = [
        "LTV использует допущения о частоте визитов и горизонте удержания — "
        "уточнить у владельца или поднять из истории чеков Эвотора (когортно).",
    ]
    return LTV(
        value=_r2(value),
        avg_check=_r2(D(avg_check)),
        visits_per_month=D(visits_per_month),
        lifespan_months=D(lifespan_months),
        margin_pct=margin_pct,
        warnings=warns,
    )
