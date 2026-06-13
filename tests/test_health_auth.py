"""Авторизация финансовых API (/api/dashboard, /api/sync).

Допуск: ?key=<DASHBOARD_TOKEN> или подпись Telegram Mini App + владелец + свежий auth_date.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse

import pytest

from backend.bot import health

BOT_TOKEN = "123:TESTTOKEN"
OWNER_ID = 483262851


def make_init_data(user_id: int = OWNER_ID, auth_date: int | None = None,
                   token: str = BOT_TOKEN) -> str:
    """Собрать initData, подписанную как это делает Telegram (схема WebAppData)."""
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AA",
        "user": json.dumps({"id": user_id, "first_name": "K"}),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


class FakeRequest:
    def __init__(self, auth: str | None = None, key: str | None = None):
        self.headers = {"Authorization": auth} if auth else {}
        self.query = {"key": key} if key else {}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", str(OWNER_ID))
    monkeypatch.setenv("DASHBOARD_TOKEN", "sekret")


def test_validate_signature():
    good = make_init_data()
    assert health.validate_telegram_data(good, BOT_TOKEN)
    assert not health.validate_telegram_data(good, "123:OTHER")
    assert not health.validate_telegram_data("", BOT_TOKEN)


def test_owner_with_fresh_initdata_allowed():
    assert health._authorize(FakeRequest(auth="tma " + make_init_data())) is None


def test_no_header_401():
    assert health._authorize(FakeRequest()).status == 401


def test_forged_hash_403():
    bad = make_init_data()[:-4] + "dead"
    assert health._authorize(FakeRequest(auth="tma " + bad)).status == 403


def test_stale_auth_date_403():
    stale = make_init_data(auth_date=int(time.time()) - health.MAX_INITDATA_AGE_SEC - 1)
    assert health._authorize(FakeRequest(auth="tma " + stale)).status == 403


def test_non_owner_403():
    stranger = make_init_data(user_id=999)
    assert health._authorize(FakeRequest(auth="tma " + stranger)).status == 403


def test_dashboard_key_fallback():
    assert health._authorize(FakeRequest(key="sekret")) is None
    assert health._authorize(FakeRequest(key="wrong")).status == 401
