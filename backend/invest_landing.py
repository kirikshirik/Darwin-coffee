"""Генератор инвест-лендинга: реальные (честные) цифры → invest_landing.html.

Лендинг для ПОКУПАТЕЛЯ бизнеса (одна страница-презентация). Берёт честный помесячный
P&L из `backend.bot.metrics.honest_month` — тот же источник, что у Telegram-бота
(годовой итог сверен с `backend.honest_report` = 334 651 ₽), — подставляет значения
в шаблон `invest_landing.template.html` и пишет самодостаточный `invest_landing.html`.

Внутренняя ops-панель — отдельный артефакт: `backend.dashboard` → `darwin_dashboard.html`.

Запуск:
    .venv/bin/python -m backend.invest_landing

Где что править:
  • вёрстка/тексты          → invest_landing.template.html
  • ВНЕШНИЕ допущения       → SALE_PRICE / ASSETS_VALUE ниже
НЕ редактируй invest_landing.html руками — он перезаписывается генератором.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal as D
from pathlib import Path

from backend import darwin_data
from backend.bot import metrics

# --- ВНЕШНИЕ допущения (НЕ из P&L владельца) --------------------------------------
SALE_PRICE = D("1300000")    # цена сделки (продажи бизнеса) — задаёт владелец
ASSETS_VALUE = D("1063000")  # оценка мат. активов — из «Таблица оценки мат.активов»

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "invest_landing.template.html"
OUTPUT = ROOT / "invest_landing.html"

ZERO = D("0")
RU_MONTHS = {
    1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
    7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек",
}


def _money(value) -> str:
    """Целые рубли с пробелом-разделителем тысяч: 311 140."""
    n = int(D(value).quantize(D("1"), rounding=ROUND_HALF_UP))
    return f"{n:,}".replace(",", " ")


def compute() -> dict:
    """Честные метрики из помесячного P&L (единый источник с ботом)."""
    rows = []  # (период, честная чистая прибыль)
    tot_rev = tot_net = ZERO
    for m in darwin_data.MONTHLY:
        period = m["period"]
        hm = metrics.honest_month(period)
        net = hm["revenue"] - hm["cogs"] - sum(hm["operating"].values(), ZERO)
        rows.append((period, net))
        tot_rev += hm["revenue"]
        tot_net += net

    n = len(rows)
    avg_rev, avg_net = tot_rev / n, tot_net / n
    payback = SALE_PRICE / avg_net if avg_net else ZERO          # цена / ср. прибыль, мес
    roi = (tot_net / SALE_PRICE * 100) if SALE_PRICE else ZERO   # годовая прибыль / цена, %

    labels = [RU_MONTHS[p.month] for p, _ in rows]
    data = [int(net.quantize(D("1"), rounding=ROUND_HALF_UP)) for _, net in rows]

    caption = (
        "Помесячная чистая прибыль за 12 месяцев — честный P&amp;L (реальный ФОТ и закупка "
        "товара). Бизнес сезонный: зимой возможны просадки в минус, летом и весной — пик. "
        f"По итогам года в плюсе: {_money(tot_net)} ₽."
    )

    return {
        "AVG_REVENUE": _money(avg_rev),
        "AVG_PROFIT": _money(avg_net),
        "ANNUAL_PROFIT": _money(tot_net),
        "ROI_PCT": str(int(roi.quantize(D("1"), rounding=ROUND_HALF_UP))),
        "PAYBACK": str(payback.quantize(D("0.1"), rounding=ROUND_HALF_UP)),
        "PAYBACK_APPROX": str(int(payback.quantize(D("1"), rounding=ROUND_HALF_UP))),
        "SALE_PRICE": _money(SALE_PRICE),
        "ASSETS_VALUE": _money(ASSETS_VALUE),
        "ASSETS_MLN": str((ASSETS_VALUE / D("1000000")).quantize(D("0.01"))),
        "CHART_LABELS": json.dumps(labels, ensure_ascii=False),
        "CHART_DATA": json.dumps(data),
        "CHART_CAPTION": caption,
    }


def render(values: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    for key, val in values.items():
        html = html.replace("{{" + key + "}}", str(val))

    leftover = sorted(set(re.findall(r"{{\s*[A-Z_]+\s*}}", html)))
    if leftover:
        raise SystemExit(f"❌ Незаполненные плейсхолдеры в шаблоне: {leftover}")

    note = (
        f"<!-- АВТОГЕНЕРАЦИЯ {datetime.now():%Y-%m-%d %H:%M} · backend/invest_landing.py · "
        "честный P&L. Не редактируй вручную — правь invest_landing.template.html. -->\n"
    )
    return html.replace("<!DOCTYPE html>", "<!DOCTYPE html>\n" + note, 1)


def main() -> None:
    values = compute()
    OUTPUT.write_text(render(values), encoding="utf-8")
    print(f"✅ Сгенерирован {OUTPUT.name} из {TEMPLATE.name}")
    print(f"   Средняя выручка:  {values['AVG_REVENUE']} ₽/мес")
    print(f"   Средняя прибыль:  {values['AVG_PROFIT']} ₽/мес (честная)")
    print(f"   Годовая прибыль:  {values['ANNUAL_PROFIT']} ₽")
    print(f"   ROI {values['ROI_PCT']}%   ·   Окупаемость {values['PAYBACK']} мес")


if __name__ == "__main__":
    main()
