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

import json
import os
import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal as D
from pathlib import Path

from sqlalchemy import func, select

from backend import darwin_data
from backend.analytics import forecast, insights as insights_mod
from backend.bot import formatting, metrics
from backend.db import SessionLocal
from backend.models import ExpenseCategory as C, Receipt

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


# --- реальные данные Эвотора для страницы «Обзор» ----------------------------

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _delta(now: D, prev: D) -> tuple[str, str]:
    if not prev:
        return "", "нет базы за прошлую неделю"
    pct = (D(now - prev) / D(prev) * 100).quantize(D("0.1"), rounding=ROUND_HALF_UP)
    return ("up" if pct >= 0 else "down"), f"{'↑' if pct >= 0 else '↓'} {abs(pct)}% к прошлой неделе"


def _kpi(cls: str, lbl: str, val: str, val_cls: str, d_cls: str, d_txt: str, sub: str) -> str:
    vc = f" {val_cls}" if val_cls else ""
    return (f'<div class="kpi {cls}"><div class="kpi-lbl">{lbl}</div>'
            f'<div class="kpi-val{vc}">{val}</div>'
            f'<div class="kpi-d {d_cls}">{d_txt}</div>'
            f'<div class="kpi-sub">{sub}</div><div class="kpi-src">эвотор</div></div>')


def _kpi_na(cls: str, lbl: str) -> str:
    return (f'<div class="kpi {cls}"><div class="kpi-lbl">{lbl}</div>'
            f'<div class="kpi-val v-muted">—</div>'
            f'<div class="kpi-d">нет данных в Эвоторе</div>'
            f'<div class="kpi-sub">не синхронизируется</div><div class="kpi-src">эвотор</div></div>')


_PAY_NAMES = {"ELECTRON": "Карта / СБП", "CASH": "Наличные", "CREDIT": "Карта / СБП"}
_PAY_COLORS = {"ELECTRON": "var(--blue)", "CREDIT": "var(--blue)", "CASH": "var(--green)"}


def _overview(period_str: str = "7d") -> dict:
    today = date.today()
    end = datetime(today.year, today.month, today.day) + timedelta(days=1)
    
    if period_str == "сег":
        start = end - timedelta(days=1)
        prev_start = start - timedelta(days=1)
        label_text = "сегодня"
        days_count = 1
    elif period_str == "вч":
        end = end - timedelta(days=1)
        start = end - timedelta(days=1)
        prev_start = start - timedelta(days=1)
        label_text = "вчера"
        days_count = 1
    elif period_str == "мес":
        start = end - timedelta(days=30)
        prev_start = start - timedelta(days=30)
        label_text = "30 дней"
        days_count = 30
    elif "_" in period_str:
        try:
            parts = period_str.split("_")
            start = datetime.strptime(parts[0], "%Y-%m-%d")
            end_parsed = datetime.strptime(parts[1], "%Y-%m-%d")
            end = end_parsed + timedelta(days=1)
            days_count = (end - start).days
            if days_count <= 0: days_count = 1
            prev_start = start - timedelta(days=days_count)
            label_text = f"{start.strftime('%d.%m')} - {end_parsed.strftime('%d.%m')}"
        except Exception:
            start = end - timedelta(days=7)
            prev_start = start - timedelta(days=7)
            label_text = "7 дней"
            days_count = 7
    else: # 7д
        start = end - timedelta(days=7)
        prev_start = start - timedelta(days=7)
        label_text = "7 дней"
        days_count = 7

    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        cur = metrics.sales_aggregate(s, biz, start, end)
        prev = metrics.sales_aggregate(s, biz, prev_start, start)
        ins = insights_mod.compute(s, biz, today)
        pay = s.execute(
            select(Receipt.payment_type, func.count(), func.coalesce(func.sum(Receipt.total_sum), ZERO))
            .where(Receipt.business_id == biz, Receipt.sold_at >= start, Receipt.sold_at < end)
            .group_by(Receipt.payment_type)
        ).all()
        hour_rows = s.execute(
            select(func.extract('hour', Receipt.sold_at), func.coalesce(func.sum(Receipt.total_sum), ZERO))
            .where(Receipt.business_id == biz, Receipt.sold_at >= start, Receipt.sold_at < end)
            .group_by(func.extract('hour', Receipt.sold_at))
        ).all()

        # Calculate current month's cumulative revenue
        start_of_month = datetime(today.year, today.month, 1)
        june_rev = s.execute(
            select(func.coalesce(func.sum(Receipt.total_sum), ZERO))
            .where(Receipt.business_id == biz, Receipt.sold_at >= start_of_month)
        ).scalar() or ZERO

        # Calculate break-even target using the latest closed month's data
        from backend.scenarios.whatif import break_even as calculate_be
        prev_month_period = metrics.latest_month_period()
        hm = metrics.honest_month(prev_month_period)
        if hm:
            expenses = {C.COGS: hm["cogs"], **hm["operating"]}
            be_info = calculate_be(hm["revenue"], expenses)
            be_target = be_info.break_even_revenue
        else:
            be_target = D("248423")  # Fallback

    checks, revenue = cur['checks'], cur['revenue']
    avg = revenue / checks if checks else ZERO
    prev_avg = prev['revenue'] / prev['checks'] if prev['checks'] else ZERO
    rev_cls, rev_txt = _delta(revenue, prev['revenue'])
    avg_cls, avg_txt = _delta(avg, prev_avg)

    progress_pct = (june_rev / be_target * 100) if be_target else ZERO
    progress_pct_float = float(progress_pct)
    progress_bar_pct = min(100.0, progress_pct_float)
    
    if june_rev >= be_target:
        progress_color = "var(--green)"
        remaining_text = '🎯 <span style="color:var(--green);font-weight:700">Цель достигнута!</span>'
    else:
        progress_color = "var(--blue)"
        remaining_sum = be_target - june_rev
        remaining_text = f'Осталось: <strong style="color:var(--ink)">{_money(remaining_sum)}₽</strong>'

    month_label = f"Прогресс за {RU_MONTHS[today.month].lower()}"

    be_html = (
        f'<div class="kpi k-be" style="grid-column: span 2; display: flex; flex-direction: column; justify-content: space-between; min-height: 106px;">'
        f'  <div style="display: flex; justify-content: space-between; align-items: flex-start; width: 100%;">'
        f'    <div>'
        f'      <div class="kpi-lbl">Точка безубыточности</div>'
        f'      <div class="kpi-val blue">{_money(be_target)}₽</div>'
        f'    </div>'
        f'    <div style="text-align: right;">'
        f'      <div class="kpi-lbl" style="color:var(--muted)">{month_label}</div>'
        f'      <div style="font-family:var(--D); font-size: 18px; font-weight: 800; color: {progress_color}; margin-top: 4px;">{progress_pct_float:.1f}%</div>'
        f'    </div>'
        f'  </div>'
        f'  '
        f'  <div style="margin-top: 10px; width: 100%;">'
        f'    <div style="width: 100%; height: 8px; background: var(--bg2); border-radius: 4px; overflow: hidden; position: relative;">'
        f'      <div style="width: {progress_bar_pct}%; height: 100%; background: {progress_color}; border-radius: 4px; transition: width 0.3s ease;"></div>'
        f'    </div>'
        f'    '
        f'    <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 6px; color: var(--muted); font-weight: 500;">'
        f'      <div>Накоплено: <strong style="color:var(--ink)">{_money(june_rev)}₽</strong></div>'
        f'      <div>{remaining_text}</div>'
        f'    </div>'
        f'  </div>'
        f'  <div class="kpi-src">расчёт</div>'
        f'</div>'
    )

    kpis = (
        _kpi('k-rev', 'Выручка', f"{_money(revenue)}₽", 'gold', rev_cls, rev_txt, f"{label_text} · {checks} чеков")
        + _kpi('k-chk', 'Средний чек', f"{_money(avg)}₽", '', avg_cls, avg_txt, f"{checks} чеков за {label_text}")
        + be_html
    )

    rows = []
    for t in ins.top_by_profit[:5]:
        margin = (t.profit / t.revenue * 100) if t.revenue else ZERO
        mcls = 'g' if margin >= 50 else ('o' if margin < 25 else '')
        rows.append(
            f'<tr><td><strong>{_esc(t.name)}</strong></td><td class="r">{_r(t.qty)}</td>'
            f'<td class="r">{_money(t.revenue)}₽</td><td class="r v-pos">{_money(t.profit)}₽</td>'
            f'<td class="r"><div class="mbar"><div class="mbar-bg">'
            f'<div class="mbar-fill {mcls}" style="width:{min(100, _r(margin))}%"></div></div>'
            f'<span style="font-size:11px;font-weight:600">{_r(margin)}%</span></div></td></tr>'
        )
    top_rows = '\n'.join(rows) or '<tr><td colspan="5" class="v-muted">Нет продаж за период</td></tr>'

    total_pay = sum((amt for _, _, amt in pay), ZERO)
    cells, electron = [], ZERO
    for pt, _cnt, amt in sorted(pay, key=lambda r: r[2], reverse=True):
        share = _r(amt / total_pay * 100) if total_pay else 0
        col = _PAY_COLORS.get(pt, '')
        style = f'color:{col}' if col else ''
        if pt in ('ELECTRON', 'CREDIT'):
            electron += amt
        pay_name = _PAY_NAMES.get(pt, pt or 'Прочее')
        cells.append(
            '<div style="text-align:center;padding:14px;background:var(--bg);border-radius:8px;border:1px solid var(--border)">'
            f'<div style="font-family:var(--D);font-size:22px;font-weight:800;{style}">{share}%</div>'
            f'<div style="font-size:11px;color:var(--muted);margin-top:3px">{pay_name}</div>'
            f'<div style="font-size:12px;font-weight:500;margin-top:2px">{_money(amt)}₽</div></div>'
        )

    hours = {int(h): amt for h, amt in hour_rows}
    vals = [int(hours.get(h, ZERO)) for h in range(24)]
    if any(vals):
        peak = max(range(24), key=lambda h: vals[h])
        share = _r(D(vals[peak]) / D(sum(vals)) * 100)
        hnote = f'<span style="color:var(--green);font-weight:600">{peak:02d}:00–{peak+1:02d}:00</span> → {share}% выручки за {label_text} (пик)'
    else:
        hnote = 'Нет продаж за период'

    wow = ins.wow
    wow_txt = 'нет сравнения' if not wow or wow.revenue_change_pct is None else f"{_r(wow.revenue_change_pct)}% к прошлой неделе"

    return {
        'EVOTOR_KPIS': kpis,
        'OV_TOP_ROWS': top_rows,
        'OV_PAY_METHODS': '\n'.join(cells),
        'OV_PAY_ACQUIRING': f'Эквайринг (карта/СБП): ~2.5% → <strong style="color:var(--red)">{_money(electron * D("0.025"))}₽/нед</strong> расход за {label_text}',
        'OV_HOURLY_VALS': json.dumps(vals),
        'OV_HOURLY_NOTE': hnote,
        'OV_WOW': wow_txt,
        'OV_WINDOW': ins.window_label,
    }


# --- сборка значений --------------------------------------------------------------
def compute(period_str: str = '7д') -> dict:
    period = metrics.latest_month_period()
    month = _month_pl(period)
    annual = _annual_pl()

    fc = forecast.forecast_history()  # следующий месяц после последнего в истории
    evotor_on = bool(os.getenv("EVOTOR_CLOUD_TOKEN", "").strip())

    op = month["operating"]
    # Бейдж «предварительно», если COGS месяца — оценка (закупки внесены не полностью):
    # см. actuals_data.effective_food_cost. Не даём headline-прибыли выглядеть завышенной.
    cogs_note = (
        f'<span class="pill-warn" style="font-size:9px;font-weight:600;margin-left:6px;'
        f'padding:1px 6px;border-radius:4px">предв. · закупки {RU_MONTHS[period.month].lower()} неполные</span>'
        if month.get("cogs_is_proxy") else ""
    )
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
        "COGS_NOTE": cogs_note,
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

        # Сценарный анализ «Что-Если» базовые данные
        "BASE_DATA_JSON": json.dumps({
            "revenue": float(month["rev"]),
            "cogs": float(month["cogs"]),
            "expenses": {
                cat.name: float(op.get(cat, ZERO))
                for cat in C if cat != C.COGS
            }
        }, ensure_ascii=False),

        # Telegram-дайджест (реальный текст бота)
        "TG_DIGEST": _tg_digest(),
        # Реальные данные Эвотора для страницы «Обзор»
        **_overview(period_str),
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


def build_html(period_str: str = '7д') -> str:
    """Собрать свежий HTML панели в память (без записи на диск) — для отдачи ботом."""
    return render(compute(period_str))


def _build_pl_json(month: dict, annual: dict, period: date) -> list[dict]:
    rows = []
    
    def add_row(label, m_val, a_val, sign="", cls="", src="расчёт", indent=False, small=False, is_section=False):
        def format_val(v):
            if v is None: return None
            if isinstance(v, str): return v
            return f"{sign}{_money(abs(v))}₽"
            
        rows.append({
            "label": label,
            "monthVal": format_val(m_val),
            "annualVal": format_val(a_val),
            "src": src,
            "cls": cls,
            "indent": indent,
            "small": small,
            "isSection": is_section
        })

    add_row("Доходы", None, None, is_section=True)
    add_row("Выручка", month["rev"], annual["rev"], cls="v-pos", src="вручную")
    add_row("Возвраты", "н/д", "н/д", src="эвотор", cls="v-muted")
    add_row("Скидки", "н/д", "н/д", src="эвотор", cls="v-muted")

    add_row("Себестоимость", None, None, is_section=True)
    add_row("Закупка товара (COGS)", month["cogs"], annual["cogs"], sign="−", cls="v-neg", src="вручную")
    add_row("Валовая прибыль", month["gross"], annual["gross"], cls="v-pos subtotal", src="расчёт")
    add_row("Маржа", f"{_pct(month['gross'], month['rev'])}%", f"{_pct(annual['gross'], annual['rev'])}%", src="", indent=True, small=True)

    add_row("Операционные расходы", None, None, is_section=True)
    for cat in OPEX_ORDER:
        a = annual["operating"].get(cat)
        if not a: continue
        m = month["operating"].get(cat)
        add_row(cat.value, m if m else None, a, sign="−", cls="v-neg", src="вручную")
        
    add_row("Итого расходов", month["opex"], annual["opex"], sign="−", cls="v-neg subtotal", src="расчёт")

    add_row("ЧИСТАЯ ПРИБЫЛЬ", month["net"], annual["net"], cls="v-gold total", src="расчёт")
    add_row("Чистая маржа", f"{_pct(month['net'], month['rev'])}%", f"{_pct(annual['net'], annual['rev'])}%", src="", indent=True, small=True)
    
    return rows

def compute_json(period_str: str = '7д') -> dict:
    """Возвращает сырые данные для рендеринга на клиенте (React)."""
    period = metrics.latest_month_period()
    month = _month_pl(period)
    annual = _annual_pl()

    fc = forecast.forecast_history()
    evotor_on = bool(os.getenv("EVOTOR_CLOUD_TOKEN", "").strip())

    # Get raw overview data
    today = date.today()
    end = datetime(today.year, today.month, today.day) + timedelta(days=1)
    
    if period_str == "сег":
        start = end - timedelta(days=1)
        prev_start = start - timedelta(days=1)
        label_text = "сегодня"
        days_count = 1
    elif period_str == "вч":
        end = end - timedelta(days=1)
        start = end - timedelta(days=1)
        prev_start = start - timedelta(days=1)
        label_text = "вчера"
        days_count = 1
    elif period_str == "мес":
        start = end - timedelta(days=30)
        prev_start = start - timedelta(days=30)
        label_text = "30 дней"
        days_count = 30
    elif "_" in period_str:
        try:
            parts = period_str.split("_")
            start = datetime.strptime(parts[0], "%Y-%m-%d")
            end_parsed = datetime.strptime(parts[1], "%Y-%m-%d")
            end = end_parsed + timedelta(days=1)
            days_count = (end - start).days
            if days_count <= 0: days_count = 1
            prev_start = start - timedelta(days=days_count)
            label_text = f"{start.strftime('%d.%m')} - {end_parsed.strftime('%d.%m')}"
        except Exception:
            start = end - timedelta(days=7)
            prev_start = start - timedelta(days=7)
            label_text = "7 дней"
            days_count = 7
    else: # 7д
        start = end - timedelta(days=7)
        prev_start = start - timedelta(days=7)
        label_text = "7 дней"
        days_count = 7

    with SessionLocal() as s:
        biz = metrics.get_business_id(s)
        cur = metrics.sales_aggregate(s, biz, start, end)
        prev = metrics.sales_aggregate(s, biz, prev_start, start)
        ins = insights_mod.compute(s, biz, today)
        pay = s.execute(
            select(Receipt.payment_type, func.count(), func.coalesce(func.sum(Receipt.total_sum), ZERO))
            .where(Receipt.business_id == biz, Receipt.sold_at >= start, Receipt.sold_at < end)
            .group_by(Receipt.payment_type)
        ).all()
        
        start_of_month = datetime(today.year, today.month, 1)
        june_rev = s.execute(
            select(func.coalesce(func.sum(Receipt.total_sum), ZERO))
            .where(Receipt.business_id == biz, Receipt.sold_at >= start_of_month)
        ).scalar() or ZERO
        
        from backend.scenarios.whatif import break_even as calculate_be
        prev_month_period = metrics.latest_month_period()
        hm = metrics.honest_month(prev_month_period)
        if hm:
            expenses = {C.COGS: hm["cogs"], **hm["operating"]}
            be_info = calculate_be(hm["revenue"], expenses)
            be_target = be_info.break_even_revenue
        else:
            be_target = D("248423")

    checks, revenue = cur['checks'], cur['revenue']
    avg = revenue / checks if checks else ZERO
    prev_avg = prev['revenue'] / prev['checks'] if prev['checks'] else ZERO
    rev_cls, rev_txt = _delta(revenue, prev['revenue'])
    avg_cls, avg_txt = _delta(avg, prev_avg)

    progress_pct = float((june_rev / be_target * 100) if be_target else ZERO)
    
    top_rows_json = []
    for t in ins.top_by_profit[:5]:
        margin = (t.profit / t.revenue * 100) if t.revenue else ZERO
        mcls = 'g' if margin >= 50 else ('o' if margin < 25 else '')
        top_rows_json.append({
            "name": t.name,
            "qty": _r(t.qty),
            "revenue": float(t.revenue),
            "revenueFormatted": _money(t.revenue),
            "profit": float(t.profit),
            "profitFormatted": _money(t.profit),
            "margin": _r(margin),
            "marginClass": mcls
        })

    wow = ins.wow
    wow_txt = 'нет сравнения' if not wow or wow.revenue_change_pct is None else f"{_r(wow.revenue_change_pct)}% к прошлой неделе"

    return {
        "periodLabel": f"{RU_MONTHS[period.month]} {period.year}",
        "evotorStatus": "Эвотор подключён" if evotor_on else "Эвотор не подключён",
        "evotorBadge": "API · онлайн" if evotor_on else "API · не подключён",
        "grossProfit": _money(month["gross"]),
        "grossMargin": _pct(month["gross"], month["rev"]),
        "netProfit": _money(month["net"]),
        "netMargin": _pct(month["net"], month["rev"]),
        "forecastValue": _money(fc.projected_net) if fc else "—",
        "forecastMonth": RU_MONTHS[fc.period.month] if fc else "—",
        "overview": {
            "wow": wow_txt,
            "window": ins.window_label,
            "label_text": label_text,
        },
        "kpis": {
            "revenue": {"val": _money(revenue), "checks": checks, "cls": rev_cls, "txt": rev_txt},
            "avgCheck": {"val": _money(avg), "cls": avg_cls, "txt": avg_txt},
            "breakEven": {"target": _money(be_target), "accumulated": _money(june_rev), "pct": progress_pct, "monthLabel": RU_MONTHS[today.month].lower()}
        },
        "topRows": top_rows_json,
        "plTable": _build_pl_json(month, annual, period),
        # Keep html fragments as fallback just in case
        "htmlFragments": compute(period_str)
    }

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
