"""Смоук JSON-слоя Mini App: структура ответа и согласованность с честным P&L.

Фиксирует контракт /api/dashboard перед рефакторингами dashboard.py: HTML-панель
и Mini App обязаны показывать одни и те же headline-цифры.
"""
from decimal import Decimal

from backend import dashboard
from backend.bot import metrics


def test_compute_json_structure(seeded_db):
    data = dashboard.compute_json("7д")
    for key in ("periodLabel", "netProfit", "grossProfit", "forecastRange",
                "overview", "kpis", "topRows", "plTable", "cogsIsProxy"):
        assert key in data, f"в JSON пропал ключ {key}"
    assert "htmlFragments" not in data
    assert set(data["kpis"]) == {"breakEven", "revenue", "avgCheck"}
    assert data["overview"]["label_text"] == "7 дней"
    assert isinstance(data["plTable"], list) and data["plTable"]


def test_compute_json_matches_honest_month(seeded_db):
    """Headline-цифры JSON = честный P&L последнего месяца (источник тот же, что у бота)."""
    period = metrics.latest_month_period()
    hm = metrics.honest_month(period)
    net = hm["revenue"] - hm["cogs"] - sum(hm["operating"].values(), Decimal("0"))
    data = dashboard.compute_json("7д")
    assert data["netProfit"] == dashboard._money(net)


def test_compute_json_periods(seeded_db):
    for p, label in (("сег", "сегодня"), ("вч", "вчера"), ("мес", "30 дней"),
                     ("2026-06-01_2026-06-07", "01.06 - 07.06")):
        assert dashboard.compute_json(p)["overview"]["label_text"] == label


def test_html_and_json_consistent(seeded_db):
    """HTML-панель (/dashboard) и JSON Mini App (/app) не расходятся в headline-цифрах."""
    html_vals = dashboard.compute("7д")
    data = dashboard.compute_json("7д")
    assert data["netProfit"] == html_vals["NP_VAL"]
    assert data["grossProfit"] == html_vals["GP_VAL"]
