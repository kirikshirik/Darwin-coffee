"""Справочник ингредиентов и закупочных цен — единый источник для тех-карт и списаний.

Зачем отдельный модуль: чтобы себестоимость пересчитывалась **динамически**. В
`cost_reference.py` per-portion суммы заморожены из Excel (молоко 16.92 ₽ и т.п.) —
поменять цену поставщика там нельзя. Здесь цена хранится в исходном виде
(молоко 94 ₽/л), а стоимость дозы считается на лету: 180 мл × 0.094 ₽/мл = 16.92 ₽.
Сменилась закупка → все тех-карты, где есть этот ингредиент, пересчитываются сами.

Два вида позиций:
  • BULK   — сыпучее/наливное, покупается в кг/л, дозируется в г/мл
             (молоко, зерно, сахар, корица). Цена → ₽ за базовую единицу (г/мл).
  • PIECE  — штучное (стакан, крышка, трубочка). Цена сразу за штуку.

Деньги — только Decimal, как и во всём проекте.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal as D
from typing import Dict

# Базовая единица дозирования для каждого вида сырья.
GRAM = "г"
ML = "мл"
PIECE = "шт"


@dataclass(frozen=True)
class Ingredient:
    """Ингредиент и его текущая закупочная цена.

    Для BULK: `purchase_price` за `purchase_qty` единиц `base_unit`
      (молоко: 94 ₽ за 1000 мл → price_per_base_unit = 0.094 ₽/мл).
    Для PIECE: `base_unit = "шт"`, `purchase_qty = 1`, цена прямо за штуку.
    """

    name: str
    base_unit: str           # г / мл / шт — в чём дозируем в тех-карте
    purchase_price: D        # сколько стоит закупка `purchase_qty` единиц
    purchase_qty: D          # объём закупки в base_unit (1000 мл, 1000 г, 1 шт)
    note: str = ""

    @property
    def is_bulk(self) -> bool:
        return self.base_unit in (GRAM, ML)

    @property
    def price_per_base_unit(self) -> D:
        """Цена одной базовой единицы (₽/г, ₽/мл или ₽/шт)."""
        return self.purchase_price / self.purchase_qty


# --- Текущие закупочные цены «Дарвина» -----------------------------------
# Сыпучее/наливное — из INPUT_PRICES в cost_reference.py (источник — Excel фуд-коста).
# Штучное (упаковка) — из per-piece сумм BASE_DRINKS. Меняйте цену здесь — и
# себестоимость во всех тех-картах, где есть ингредиент, пересчитается.
#
# TODO(owner): подтвердить актуальные цены поставщика и спорные позиции:
#   • корица — заявлено 40 ₽/8 г (=5 ₽/г), но в расчёте владельца 1.6 ₽/г (Находка 3);
#   • зерно — в расчёте округлено до 38 ₽/порция (=2.235 ₽/г) против 2.2 ₽/г по 2200 ₽/кг.
CATALOG: Dict[str, Ingredient] = {
    # BULK
    "молоко":  Ingredient("молоко", ML,   D("94"),   D("1000"), "94 ₽/л"),
    "зерно":   Ingredient("зерно",  GRAM, D("2200"), D("1000"), "2200 ₽/кг (кофе в зерне)"),
    "сахар":   Ingredient("сахар",  GRAM, D("60"),   D("1000"), "60 ₽/кг"),
    "корица":  Ingredient("корица", GRAM, D("40"),   D("8"),    "40 ₽/8 г — цена спорна, см. Находку 3"),
    # PIECE — упаковка зависит от размера стакана, поэтому ведём варианты.
    "стакан_250":   Ingredient("стакан_250",   PIECE, D("2.62"), D("1")),
    "стакан_350":   Ingredient("стакан_350",   PIECE, D("3.64"), D("1")),
    "стакан_450":   Ingredient("стакан_450",   PIECE, D("4.49"), D("1")),
    "крышка_250":   Ingredient("крышка_250",   PIECE, D("1.80"), D("1")),
    "крышка_350":   Ingredient("крышка_350",   PIECE, D("1.95"), D("1")),
    "крышка_450":   Ingredient("крышка_450",   PIECE, D("1.95"), D("1")),
    "монжет":       Ingredient("монжет",       PIECE, D("1.75"), D("1")),
    "подстаканник": Ingredient("подстаканник", PIECE, D("2.83"), D("1")),
    "палочка":      Ingredient("палочка",      PIECE, D("0.50"), D("1")),
    "трубочка":     Ingredient("трубочка",     PIECE, D("0.50"), D("1")),
    "стики":        Ingredient("стики",        PIECE, D("1.50"), D("1")),
    # Допы — закупочная цена и фасовка из листа «Добавки» Excel (A56:E64).
    # Сливки и арахисовая паста: в Excel цена/доза есть, но себестоимость порции
    # не посчитана (ADDONS_NO_COST). Динамический движок её добивает.
    "какао":            Ingredient("какао",            GRAM, D("119"), D("100"),  "119 ₽/100 г"),
    "ванильный_сахар":  Ingredient("ванильный_сахар",  GRAM, D("390"), D("1000"), "390 ₽/кг"),
    "матча":            Ingredient("матча",            GRAM, D("345"), D("160"),  "345 ₽/160 г"),
    "порошки":          Ingredient("порошки",          GRAM, D("701"), D("1000"), "701 ₽/кг"),
    "сироп":            Ingredient("сироп",            ML,   D("300"), D("1000"), "300 ₽/л"),
    "сливки":           Ingredient("сливки",           ML,   D("199"), D("1000"), "199 ₽/л (в Excel себест. порции не посчитана)"),
    "арахисовая_паста": Ingredient("арахисовая_паста", GRAM, D("180"), D("250"),  "180 ₽/250 г (в Excel себест. порции не посчитана)"),
}


def get(name: str) -> Ingredient:
    if name not in CATALOG:
        raise KeyError(f"Нет ингредиента «{name}» в справочнике: {sorted(CATALOG)}")
    return CATALOG[name]


def price_per_base_unit(name: str) -> D:
    """Текущая цена базовой единицы ингредиента (₽/г, ₽/мл, ₽/шт)."""
    return get(name).price_per_base_unit


def with_price(name: str, purchase_price: D, purchase_qty: D | None = None) -> Ingredient:
    """Копия ингредиента с новой закупочной ценой — для «что если» по поставщику.

    Не мутирует CATALOG: сценарий «молоко подорожало на 10%» строит новый прайс
    и передаёт его в тех-карту, не трогая базовый справочник.
    """
    base = get(name)
    return Ingredient(
        name=base.name,
        base_unit=base.base_unit,
        purchase_price=D(purchase_price),
        purchase_qty=D(purchase_qty) if purchase_qty is not None else base.purchase_qty,
        note=base.note,
    )


def price_book(overrides: Dict[str, Ingredient] | None = None) -> Dict[str, D]:
    """Снимок цен «ингредиент → ₽/базовая единица» с возможными переопределениями.

    `overrides` — ингредиенты с изменённой ценой (из `with_price`/`bump_price`).
    Тех-карта считает себестоимость по этому снимку → один прайс, много рецептов.
    """
    book = {name: ing.price_per_base_unit for name, ing in CATALOG.items()}
    for name, ing in (overrides or {}).items():
        book[name] = ing.price_per_base_unit
    return book


def bump_price(name: str, pct: D) -> Ingredient:
    """Ингредиент с ценой, изменённой на `pct` процентов (+10 = подорожание на 10%)."""
    base = get(name)
    factor = (D("100") + D(pct)) / D("100")
    return with_price(name, base.purchase_price * factor, base.purchase_qty)
