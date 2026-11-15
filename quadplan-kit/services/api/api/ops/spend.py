"""Daily LLM spend alarm (prompt 12): sum today's `llm_call.cost_usd` and log an alarm when it
passes `LLM_SPEND_ALARM_USD`. The worker runs it every hour; `llm_call` holds no user data."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.db import models as m

log = logging.getLogger("api.ops.spend")


@dataclass(frozen=True)
class Spend:
    day: dt.date
    usd: Decimal
    calls: int
    limit: Decimal
    alarm: bool


def check_spend(db: Session, limit_usd: float, today: dt.date | None = None) -> Spend:
    today = today or dt.datetime.now(dt.UTC).date()
    usd, calls = db.execute(
        sa.select(sa.func.coalesce(sa.func.sum(m.LlmCall.cost_usd), 0), sa.func.count()).where(
            m.LlmCall.created_day == today
        )
    ).one()
    limit = Decimal(str(limit_usd))
    spend = Spend(today, Decimal(usd), int(calls), limit, Decimal(usd) > limit)
    if spend.alarm:
        log.error(
            "LLM SPEND ALARM: $%s spent on %s across %d calls (limit $%s)",
            spend.usd, today, spend.calls, limit,
        )  # fmt: skip
    return spend
