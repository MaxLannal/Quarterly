"""Prompt 12 operations: the daily LLM spend alarm."""

from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

import pytest
import sqlalchemy as sa
from api.db import models as m
from api.ops.spend import check_spend
from sqlalchemy.orm import Session


@pytest.mark.db
def test_spend_alarm(migrated_db_url: str, caplog: pytest.LogCaptureFixture) -> None:
    engine = sa.create_engine(migrated_db_url)
    today = dt.date(2026, 11, 15)
    with Session(engine) as db:
        for cost, day in ((2.5, today), (2.0, today), (9.0, today - dt.timedelta(days=1))):
            db.add(
                m.LlmCall(task="a2_advisor_chat", model="x", prompt_version="1", in_tokens=1,
                          out_tokens=1, cost_usd=Decimal(str(cost)), latency_ms=1, ok=True,
                          created_day=day)
            )  # fmt: skip
        db.flush()
        quiet = check_spend(db, 5.0, today)
        assert (quiet.usd, quiet.calls, quiet.alarm) == (Decimal("4.5"), 2, False)
        with caplog.at_level(logging.ERROR, logger="api.ops.spend"):
            loud = check_spend(db, 4.0, today)
        assert loud.alarm and "LLM SPEND ALARM" in caplog.text and "$4.5" in caplog.text
    engine.dispose()


def test_client_address_behind_caddy_and_nginx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec review (final): with Caddy in front of nginx the client is 2 hops back; a spoofed
    header from the client cannot move it."""
    from api.auth.ratelimit import client_ip
    from api.config import get_settings
    from starlette.requests import Request

    def request(xff: str) -> Request:
        scope = {
            "type": "http",
            "headers": [(b"x-forwarded-for", xff.encode())],
            "client": ("172.18.0.9", 1234),
        }
        return Request(scope)  # type: ignore[arg-type]

    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 2)
    assert client_ip(request("203.0.113.7, 172.18.0.5")) == "203.0.113.7"
    assert client_ip(request("6.6.6.6, 203.0.113.7, 172.18.0.5")) == "203.0.113.7"
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 1)
    assert client_ip(request("6.6.6.6, 203.0.113.7")) == "203.0.113.7"
