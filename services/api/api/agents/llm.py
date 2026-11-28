"""The process-wide LLM client of the API (`llm_gateway.api.get_llm`).

The real gateway is configured only with `LLM_LIVE=true` and at least one provider key; until
then `get_llm()` stays `UnavailableLLM` and every agent takes its fallback. Calls made outside
an agent run (for example the forum's moderation call) are logged to `llm_call` here.
"""

from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

from llm_gateway.api import CallRecord, set_llm
from llm_gateway.gateway import build_gateway
from sqlalchemy.orm import Session

from api.config import Settings
from api.db import models as m
from api.db.session import get_engine

logger = logging.getLogger("api.agents")


def db_sink(record: CallRecord) -> None:
    """Write one `llm_call` row in its own transaction (no user identifier)."""
    with Session(get_engine()) as db:
        db.add(
            m.LlmCall(
                task=record.task[:48],
                model=record.model[:64],
                prompt_version=record.prompt_version[:32],
                in_tokens=record.in_tokens,
                out_tokens=record.out_tokens,
                cost_usd=Decimal(f"{record.cost_usd:.6f}"),
                latency_ms=record.latency_ms,
                ok=record.ok,
                created_day=dt.date.today(),
            )
        )
        db.commit()


def configure_llm(settings: Settings) -> bool:
    """Install the real gateway when allowed and configured; returns whether it did."""
    if settings.llm_fake == "e2e" and settings.environment in ("development", "test"):
        from api.agents.e2e_llm import e2e_llm

        set_llm(e2e_llm())
        logger.warning("LLM_FAKE=e2e: model requests get canned test answers")
        return True
    if not settings.llm_live:
        return False  # leave the current client (UnavailableLLM, or a test's fake) alone
    gateway = build_gateway(
        anthropic_api_key=settings.anthropic_api_key.get_secret_value(),
        openrouter_api_key=settings.openrouter_api_key.get_secret_value(),
        anthropic_base_url=settings.anthropic_base_url or None,
        sink=db_sink,
    )
    if gateway is None:
        logger.warning("LLM_LIVE is on but no provider key is set; agents use their fallbacks")
        return False
    set_llm(gateway)
    return True
