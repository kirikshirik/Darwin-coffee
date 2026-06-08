"""Тех-карты и динамический фуд-кост.

Тех-карта = рецепт: список компонентов (ингредиент + доза). Себестоимость порции
**считается на лету** из текущих закупочных цен (`ingredients.price_book`), а не
берётся замороженной из Excel. Поэтому при изменении цены поставщика (молоко, зерно)
себестоимость каждого напитка, где этот ингредиент есть, пересчитывается сама —
это и есть «динамический расчёт фуд-коста и тех-карт».

Связь с `cost_reference.py`:
  • `cost_reference` — замороженный per-portion расчёт владельца из Excel (контроль
    67.82 / 77.45 / 79.24 ₽). Его не трогаем — он источник правды по сверке.
  • Здесь — живая модель: те же дозы, но стоимость из прайса. `reconcile()` сверяет
    динамический итог с замороженным контролем и раскладывает расхождение по
    компонентам — автоматически вскрывая Находку 3 (округление зерна, спор по корице).

Деньги — только Decimal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal as D, ROUND_HALF_UP
from typing import Dict, List, Mapping, Optional

from backend.costing import ingredients as ing
from backend import cost_reference as cr

ZERO = D("0")


def _r2(x: D) -> D:
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Component:
    """Один компонент тех-карты: сколько ингредиента уходит на порцию.

    `dose` — в базовой единице ингредиента (180 мл молока, 17 г зерна, 1 шт стакан).
    """

    ingredient: str
    dose: D

    def cost(self, prices: Mapping[str, D]) -> D:
        if self.ingredient not in prices:
            raise KeyError(f"Нет цены для «{self.ingredient}» в прайсе")
        return self.dose * prices[self.ingredient]


@dataclass(frozen=True)
class TechCard:
    """Рецепт напитка: набор компонентов (+ опциональный объём для справки)."""

    name: str
    components: List[Component]
    volume_ml: Optional[int] = None

    def cost(self, prices: Mapping[str, D] | None = None) -> D:
        """Себестоимость порции по текущему (или переданному) прайсу, ₽."""
        book = prices if prices is not None else ing.price_book()
        return sum((c.cost(book) for c in self.components), ZERO)

    def breakdown(self, prices: Mapping[str, D] | None = None) -> List[dict]:
        """Раскладка стоимости по компонентам — для тех-карты на экране."""
        book = prices if prices is not None else ing.price_book()
        rows = []
        for c in self.components:
            unit_price = book.get(c.ingredient, ZERO)
            rows.append({
                "ingredient": c.ingredient,
                "dose": c.dose,
                "unit": ing.get(c.ingredient).base_unit if c.ingredient in ing.CATALOG else "",
                "unit_price": unit_price,
                "cost": _r2(c.dose * unit_price),
            })
        return rows


# --- Тех-карты базовых позиций «Дарвина» ----------------------------------
# Дозы из docs/DATA.md §6 и аудита (cost_reference.RAW_AUDIT). Кофе/сахар/корица
# одинаковы во всех объёмах; различаются молоко и размер упаковки.
_COMMON = [
    Component("зерно", D("17")),
    Component("сахар", D("10")),
    Component("корица", D("0.5")),
    Component("монжет", D("1")),
    Component("подстаканник", D("1")),
    Component("палочка", D("1")),
    Component("трубочка", D("1")),
    Component("стики", D("1")),
]

BASE_CARDS: Dict[int, TechCard] = {
    250: TechCard("Базовый напиток 250 мл", [
        Component("молоко", D("180")),
        Component("стакан_250", D("1")),
        Component("крышка_250", D("1")),
        *_COMMON,
    ], volume_ml=250),
    350: TechCard("Базовый напиток 350 мл", [
        Component("молоко", D("270")),
        Component("стакан_350", D("1")),
        Component("крышка_350", D("1")),
        *_COMMON,
    ], volume_ml=350),
    450: TechCard("Базовый напиток 450 мл", [
        Component("молоко", D("280")),
        Component("стакан_450", D("1")),
        Component("крышка_450", D("1")),
        *_COMMON,
    ], volume_ml=450),
}


def base_card(volume_ml: int) -> TechCard:
    if volume_ml not in BASE_CARDS:
        raise KeyError(f"Нет тех-карты для {volume_ml} мл: {sorted(BASE_CARDS)}")
    return BASE_CARDS[volume_ml]


# --- Допы (лист «Добавки» Excel) ------------------------------------------
# Доза допа на порцию в базовой единице ингредиента (Excel A56:E64, колонка D).
# Сливки 270 мл — это, по сути, порция РАФа. Себестоимость считается динамически,
# в т.ч. для сливок/арахиса, которым в Excel себестоимость порции не заполнили.
ADDON_DOSES: Dict[str, D] = {
    "какао": D("10"),
    "ванильный_сахар": D("10"),
    "матча": D("3"),
    "порошки": D("15"),
    "сироп": D("20"),
    "сливки": D("270"),
    "арахисовая_паста": D("15"),
}

# Имена допов в cost_reference (там с пробелами) ↔ наши ингредиенты (с подчёркиванием).
_ADDON_FROZEN_NAME = {
    "ванильный_сахар": "ванильный сахар",
    "арахисовая_паста": "арахисовая паста",
}


def addon_card(name: str) -> TechCard:
    if name not in ADDON_DOSES:
        raise KeyError(f"Нет допа «{name}»: {sorted(ADDON_DOSES)}")
    return TechCard(f"Доп: {name}", [Component(name, ADDON_DOSES[name])])


def addon_cost(name: str, prices: Mapping[str, D] | None = None) -> D:
    """Себестоимость порции допа по текущему прайсу, ₽."""
    return addon_card(name).cost(prices)


def drink_card(volume_ml: int, *addons: str) -> TechCard:
    """Полная тех-карта: базовая позиция + перечисленные допы."""
    base = base_card(volume_ml)
    comps = list(base.components)
    for a in addons:
        if a not in ADDON_DOSES:
            raise KeyError(f"Нет допа «{a}»: {sorted(ADDON_DOSES)}")
        comps.append(Component(a, ADDON_DOSES[a]))
    name = base.name + (" + " + " + ".join(addons) if addons else "")
    return TechCard(name, comps, volume_ml=volume_ml)


def reconcile_addons() -> List[dict]:
    """Сверяет динамическую себестоимость допов с замороженными в cost_reference.

    Вскрывает расхождения (матча, ванильный сахар) и добивает сливки/арахис,
    которым в Excel себестоимость порции не посчитали.
    """
    book = ing.price_book()
    rows = []
    for name in ADDON_DOSES:
        dynamic = _r2(addon_cost(name, book))
        frozen_name = _ADDON_FROZEN_NAME.get(name, name)
        frozen = cr.ADDONS.get(frozen_name)
        if frozen is None:
            status = "новый (в Excel себест. порции не было)"
            delta = None
        else:
            frozen = _r2(frozen)
            delta = _r2(dynamic - frozen)
            status = "совпало" if delta == 0 else "расхождение"
        rows.append({
            "addon": name,
            "dynamic": dynamic,
            "frozen": frozen,
            "delta": delta,
            "status": status,
        })
    return rows


def recompute_on_price_change(name: str, pct: D) -> List[dict]:
    """Как изменится себестоимость каждой базовой позиции при сдвиге цены ингредиента.

    Сердце «динамического фуд-коста»: меняем закупку (`name` на `pct`%) и сразу
    видим новую себестоимость всех напитков, где ингредиент участвует.
    Возвращает по позиции: было / стало / Δ ₽.
    """
    base_book = ing.price_book()
    new_book = ing.price_book({name: ing.bump_price(name, pct)})
    rows = []
    for vol, card in sorted(BASE_CARDS.items()):
        was, now = card.cost(base_book), card.cost(new_book)
        rows.append({
            "volume_ml": vol,
            "was": _r2(was),
            "now": _r2(now),
            "delta": _r2(now - was),
        })
    return rows


@dataclass
class Reconciliation:
    volume_ml: int
    dynamic: D          # себестоимость по живому прайсу
    documented: D       # замороженный контроль из cost_reference.CONTROL
    delta: D            # dynamic − documented
    component_deltas: List[dict] = field(default_factory=list)


def reconcile(volume_ml: int) -> Reconciliation:
    """Сверяет динамическую себестоимость с замороженным Excel-контролем.

    Раскладывает расхождение по компонентам — где живой расчёт по закупочным
    ценам расходится с per-portion суммами владельца (Находка 3: зерно, корица).
    """
    card = base_card(volume_ml)
    book = ing.price_book()
    dynamic = card.cost(book)
    documented = cr.CONTROL[volume_ml]

    # Расхождение по сопоставимым компонентам (где cost_reference хранит сумму).
    frozen = cr.BASE_DRINKS[volume_ml]
    name_map = {"зерно": "кофе"}  # в cost_reference кофе назван «кофе», у нас «зерно»
    comp_deltas = []
    for c in card.components:
        frozen_key = name_map.get(c.ingredient, c.ingredient)
        # упаковочные варианты (стакан_250) в cost_reference без суффикса
        if frozen_key not in frozen:
            frozen_key = c.ingredient.split("_")[0]
        if frozen_key not in frozen:
            continue
        live = _r2(c.cost(book))
        doc = _r2(frozen[frozen_key])
        if live != doc:
            comp_deltas.append({
                "ingredient": c.ingredient,
                "dynamic": live,
                "documented": doc,
                "delta": _r2(live - doc),
            })
    return Reconciliation(
        volume_ml=volume_ml,
        dynamic=_r2(dynamic),
        documented=_r2(documented),
        delta=_r2(dynamic - documented),
        component_deltas=comp_deltas,
    )
