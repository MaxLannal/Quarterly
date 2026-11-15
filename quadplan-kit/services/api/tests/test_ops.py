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
