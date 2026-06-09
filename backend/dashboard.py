"""Генератор внутренней ops-панели: реальные данные → darwin_dashboard.html.

Это панель для ВЛАДЕЛЬЦА (внутренняя аналитика), а не инвест-лендинг
(тот — отдельный артефакт: `backend.invest_landing` → invest_landing.html).

Реальные данные берутся из того же честного P&L, что и у бота
(`backend.bot.metrics` / `backend.honest_report`). Панель спроектирована под живой
поэлементный Эвотор (по часам, чеки, возвраты, способы оплаты, дневные/товарные
продажи) — а Эвотор ещё НЕ подключён (EVOTOR_CLOUD_TOKEN пуст). Поэтому такие панели
остаются с демо-числами и помечаются в шаблоне бейджем «демо · ждёт Эвотора».

ЧЕМ НАПОЛНЕНО РЕАЛЬНО: P&L (последний месяц + 12 мес), расчётные KPI (валовая/чистая
прибыль, прогноз), форма расходов, Telegram-дайджест, статус подключения Эвотора.

Запуск:
    .venv/bin/python -m backend.dashboard

Вёрстку правь в darwin_dashboard.template.html; darwin_dashboard.html — сборка,
руками не редактировать.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal as D
from pathlib import Path

from backend import darwin_data
from backend.analytics import forecast
from backend.bot import formatting, metrics
from backend.models import ExpenseCategory as C

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "darwin_dashboard.template.html"
OUTPUT = ROOT / "darwin_dashboard.html"

ZERO = D("0")
RU_MONTHS = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

# Порядок строк операционных расходов в P&L (категории без значений за год скрываются).
OPEX_ORDER = [
    C.RENT, C.PAYROLL, C.UTILITIES, C.ACQUIRING, C.TAXES,
    C.MARKETING, C.DEPRECIATION, C.SOFTWARE, C.COMMS_SECURITY,
]


def _r(value) -> int:
    return int(D(value).quantize(D("1"), rounding=ROUND_HALF_UP))


def _money(value) -> str:
    """Целые рубли с пробелом-разделителем тысяч: 311 140."""
    return f"{_r(value):,}".replace(",", " ")


def _pct(part, whole) -> str:
    return f"{(D(part) / D(whole) * 100).quantize(D('0.1'), rounding=ROUND_HALF_UP)}" if whole else "—"


# --- расчёт честного P&L ----------------------------------------------------------
def _month_pl(period: date) -> dict:
    hm = metrics.honest_month(period)
    rev, cogs = hm["revenue"], hm["cogs"]
    operating = dict(hm["operating"])
    opex = sum(operating.values(), ZERO)
    gross = rev - cogs
    net = gross - opex
    return {"rev": rev, "cogs": cogs, "operating": operating, "opex": opex,
            "gross": gross, "net": net, "cogs_is_proxy": hm["cogs_is_proxy"]}


def _annual_pl() -> dict:
    rev = cogs = opex = ZERO
    operating: dict = {}
    for m in darwin_data.MONTHLY:
        pl = _month_pl(m["period"])
        rev += pl["rev"]
        cogs += pl["cogs"]
        opex += pl["opex"]
        for cat, amt in pl["operating"].items():
            operating[cat] = operating.get(cat, ZERO) + amt
    gross = rev - cogs
    return {"rev": rev, "cogs": cogs, "operating": operating, "opex": opex,
            "gross": gross, "net": gross - opex}


# --- HTML-блоки -------------------------------------------------------------------
def _pl_row(label: str, m_val, a_val, *, sign="", cls="", src="расчёт",
            indent=False, small=False) -> str:
    """Строка P&L: статья · месяц · 12 мес · источник."""
    def cell(v):
        if v is None:
            return '<div class="pl-c r v-muted">—</div>'
        txt = (sign + _money(abs(v)) + "₽") if not isinstance(v, str) else v
        return f'<div class="pl-c r {cls}">{txt}</div>'

    src_html = f'<span class="src {_SRC_CLS.get(src, "calc")}">{src}</span>' if src else ""
    lbl_style = ' style="font-size:11px;padding-left:28px"' if indent else ""
    lbl_cls = " v-muted" if small else ""
    return (f'<div class="pl-row{ " " + cls if cls in ("subtotal","total","section") else ""}">'
            f'<div class="pl-c{lbl_cls}"{lbl_style}>{label}</div>'
            f'{cell(m_val)}{cell(a_val)}'
            f'<div class="pl-c r">{src_html}</div></div>')


_SRC_CLS = {"эвотор": "evo", "вручную": "man", "расчёт": "calc"}


def _section_row(title: str) -> str:
    return (f'<div class="pl-row section"><div class="pl-c">{title}</div>'
            f'<div class="pl-c"></div><div class="pl-c"></div><div class="pl-c"></div></div>')


def _build_pl_table(month: dict, annual: dict, period: date) -> str:
    rows = [
        '<div class="pl-row hdr"><div class="pl-c">Статья</div>'
        f'<div class="pl-c r">{RU_MONTHS[period.month]} {period.year}</div>'
        '<div class="pl-c r">12 мес · факт</div><div class="pl-c r">Источник</div></div>',

        _section_row("Доходы"),
        _pl_row("Выручка", month["rev"], annual["rev"], cls="v-pos", src="вручную"),
        _pl_row("Возвраты", "<span class=\"v-muted\">н/д</span>", "<span class=\"v-muted\">н/д</span>", src="эвотор"),
        _pl_row("Скидки", "<span class=\"v-muted\">н/д</span>", "<span class=\"v-muted\">н/д</span>", src="эвотор"),

        _section_row("Себестоимость"),
        _pl_row("Закупка товара (COGS)", month["cogs"], annual["cogs"], sign="−", cls="v-neg", src="вручную"),
        _pl_row("Валовая прибыль", month["gross"], annual["gross"], cls="v-pos subtotal", src="расчёт"),
        _pl_row("Маржа", f"{_pct(month['gross'], month['rev'])}%",
                f"{_pct(annual['gross'], annual['rev'])}%", src="", indent=True, small=True),

        _section_row("Операционные расходы"),
    ]
    for cat in OPEX_ORDER:
        a = annual["operating"].get(cat)
        if not a:
            continue
        m = month["operating"].get(cat)
        rows.append(_pl_row(cat.value, m if m else None, a, sign="−", cls="v-neg", src="вручную"))
    rows.append(_pl_row("Итого расходов", month["opex"], annual["opex"], sign="−", cls="v-neg subtotal", src="расчёт"))

    rows.append(
        '<div class="pl-row total"><div class="pl-c">ЧИСТАЯ ПРИБЫЛЬ</div>'
        f'<div class="pl-c r v-gold">{_money(month["net"])}₽</div>'
        f'<div class="pl-c r v-gold">{_money(annual["net"])}₽</div>'
        '<div class="pl-c r"><span class="src calc">расчёт</span></div></div>')
    rows.append(_pl_row("Чистая маржа", f"{_pct(month['net'], month['rev'])}%",
                        f"{_pct(annual['net'], annual['rev'])}%", src="", indent=True, small=True))
    return "\n".join(rows)


def _tg_digest() -> str:
    """Реальный текст месячного дайджеста бота → HTML-строки для предпросмотра."""
    text = formatting.format_period(metrics.monthly_report())
    return text.replace("\n", "<br>")


# --- сборка значений --------------------------------------------------------------
def compute() -> dict:
    period = metrics.latest_month_period()
    month = _month_pl(period)
    annual = _annual_pl()

    fc = forecast.forecast_history()  # следующий месяц после последнего в истории
    evotor_on = bool(os.getenv("EVOTOR_CLOUD_TOKEN", "").strip())

    op = month["operating"]
    return {
        "PERIOD_LABEL": f"{RU_MONTHS[period.month]} {period.year}",
        "TODAY_LABEL": f"{date.today():%d.%m.%Y}",
        "EVOTOR_STATUS": "Эвотор подключён" if evotor_on else "Эвотор не подключён",
        "EVOTOR_SUBSTATUS": "Синхронизация активна" if evotor_on else "Демо-режим · только Excel-данные",
        "EVOTOR_BADGE": "API · онлайн" if evotor_on else "API · не подключён",

        # Расчётные KPI (последний месяц)
        "GP_VAL": _money(month["gross"]),
        "GP_MARGIN": _pct(month["gross"], month["rev"]),
        "NP_VAL": _money(month["net"]),
        "NP_MARGIN": _pct(month["net"], month["rev"]),
        "FC_VAL": _money(fc.projected_net) if fc else "—",
        "FC_MONTH": RU_MONTHS[fc.period.month] if fc else "—",

        # P&L
        "PL_TABLE": _build_pl_table(month, annual, period),

        # Форма расходов (последний месяц, реальные статьи)
        "EXP_RENT": _money(op.get(C.RENT, ZERO)),
        "EXP_PAYROLL": _money(op.get(C.PAYROLL, ZERO)),
        "EXP_UTIL": _money(op.get(C.UTILITIES, ZERO)),
        "EXP_TAXES": _money(op.get(C.TAXES, ZERO)),
        "EXP_ACQ": _money(op.get(C.ACQUIRING, ZERO)),
        "EXP_COGS": _money(month["cogs"]),
        "EXP_TOTAL": _money(month["opex"] + month["cogs"]),

        # Telegram-дайджест (реальный текст бота)
        "TG_DIGEST": _tg_digest(),
    }


def render(values: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    for key, val in values.items():
        html = html.replace("{{" + key + "}}", str(val))

    leftover = sorted(set(re.findall(r"{{\s*[A-Z_]+\s*}}", html)))
    if leftover:
        raise SystemExit(f"❌ Незаполненные плейсхолдеры в шаблоне: {leftover}")

    note = (
        f"<!-- АВТОГЕНЕРАЦИЯ {datetime.now():%Y-%m-%d %H:%M} · backend/dashboard.py · "
        "реальный P&L + демо-панели Эвотора. Правь darwin_dashboard.template.html. -->\n"
    )
    return html.replace("<!DOCTYPE html>", "<!DOCTYPE html>\n" + note, 1)


def build_html() -> str:
    """Собрать свежий HTML панели в память (без записи на диск) — для отдачи ботом."""
    return render(compute())


def main() -> None:
    values = compute()
    OUTPUT.write_text(render(values), encoding="utf-8")
    print(f"✅ Сгенерирован {OUTPUT.name} из {TEMPLATE.name}")
    print(f"   Период:           {values['PERIOD_LABEL']}")
    print(f"   Валовая прибыль:  {values['GP_VAL']} ₽ ({values['GP_MARGIN']}%)")
    print(f"   Чистая прибыль:   {values['NP_VAL']} ₽ ({values['NP_MARGIN']}%)")
    print(f"   Прогноз ({values['FC_MONTH']}): {values['FC_VAL']} ₽")
    print(f"   Эвотор:           {values['EVOTOR_STATUS']}")


if __name__ == "__main__":
    main()
