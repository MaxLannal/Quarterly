"""The agent endpoints (prompt 07): the plan generator (A1) and the advisor chat (A2), both
streamed as Server-Sent Events.

Both work without a configured LLM: the generator falls back to the default elective ranking
and no rationale, and the advisor still handles typed confirmations. Logged-out use is allowed
and rate-limited by a Redis-only counter keyed by a hash of the client address and the day
(never written to disk); a logged-in account has its own daily limit.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from llm_gateway.api import LLM, get_llm
from planner_core import verify_checked
from planner_core.generator import horizon
from planner_core.hashing import plan_hash
from planner_core.models import PlanState
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.agents.chat import ChatRun, history, purge_old_history
from api.agents.generate import GenerateRun
from api.agents.runtime import SSE_HEADERS, RunLog, new_run, sse
from api.agents.tools import ToolBox
from api.auth.ratelimit import DAY, Limit, account_subject, ip_subject
from api.auth.sessions import SessionData, current_account, optional_session
from api.auth.store import Store, get_store
from api.config import get_settings
from api.db import models as m
from api.db.session import get_session
from api.repo import catalog as catalog_repo
from api.repo import plans as plans_repo
from api.repo.rules import UnknownProgramsError, load_verify_inputs
from api.schemas.agents import (
    AgentEvent,
    ChatHistory,
    ChatRequest,
    ErrorEvent,
    GenerateRequest,
)

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger("api.agents")

Db = Annotated[Session, Depends(get_session)]
Llm = Annotated[LLM, Depends(get_llm)]
MaybeSession = Annotated[SessionData | None, Depends(optional_session)]
RedisStore = Annotated[Store, Depends(get_store)]

#: SPEC "A1": 10 generations per account per day; 3 per client address when logged out.
GENERATE_PER_ACCOUNT = Limit("agent-generate:account", 10, DAY)
GENERATE_PER_IP = Limit("agent-generate:ip", 3, DAY)
#: Advisor messages per day (not in the SPEC; see docs/OPEN_QUESTIONS.md "Prompt 07").
CHAT_PER_ACCOUNT = Limit("agent-chat:account", 60, DAY)
CHAT_PER_IP = Limit("agent-chat:ip", 30, DAY)

SSE: dict[int | str, dict[str, Any]] = {
    200: {
        "model": AgentEvent,
        "description": "Server-Sent Events; each `data:` line is one AgentEvent as JSON.",
        "content": {"text/event-stream": {}},
    }
}

FAILED = "Something went wrong on our side. Try again."


def _unpublished() -> bool:
    return get_settings().show_unpublished_programs


def _statuses() -> tuple[str, ...]:
    return catalog_repo.ALL_STATUSES if _unpublished() else catalog_repo.PUBLISHED


def _account(db: Session, session: SessionData | None) -> m.Account | None:
    return db.get(m.Account, session.account_id) if session is not None else None


def _limit(
    store: Store,
    request: Request,
    account: m.Account | None,
    per_account: Limit,
    per_ip: Limit,
) -> None:
    if account is not None:
        per_account.hit(store, account_subject(account.id))
    else:
        per_ip.hit(store, ip_subject(request))


def _saved_plan(
    db: Session, account: m.Account | None, plan_id: str | None, state: PlanState
) -> m.Plan | None:
    """The account's saved plan, if the request names one and its plan is unchanged since it
    was saved. Another account's plan is a 404."""
    if account is None or not plan_id:
        return None
    try:
        plan = plans_repo.owned_plan(db, account.id, uuid.UUID(plan_id))
    except (ValueError, plans_repo.PlanNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Plan not found.") from exc
    if plan_hash(plans_repo.read_state(db, plan)) != plan_hash(state):
        return None
    return plan


def _stream(db: Session, events: Iterator[BaseModel]) -> StreamingResponse:
    def body() -> Iterator[str]:
        try:
            for event in events:
                yield sse(event)
        except Exception:
            logger.exception("agent run failed")  # no request data in the message
            db.rollback()
            yield sse(ErrorEvent(message=FAILED))

    return StreamingResponse(body(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/generate", response_class=StreamingResponse, responses=SSE)
def generate(
    body: GenerateRequest,
    request: Request,
    db: Db,
    store: RedisStore,
    session: MaybeSession,
    llm: Llm,
) -> StreamingResponse:
    account = _account(db, session)
    _limit(store, request, account, GENERATE_PER_ACCOUNT, GENERATE_PER_IP)
    saved = _saved_plan(db, account, body.plan_id, body.plan)
    try:
        rules, catalog = load_verify_inputs(
            db,
            body.plan,
            show_unpublished=_unpublished(),
            whole_catalog=True,
            section_terms=horizon(body.plan),
        )
    except UnknownProgramsError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unknown program(s): {', '.join(exc.program_ids)}"
        ) from exc
    report, _ = verify_checked(body.plan, rules, catalog)
    box = ToolBox(
        db=db,
        state=body.plan,
        report=report,
        statuses=_statuses(),
        show_unpublished=_unpublished(),
        logged_in=account is not None,
    )
    run = GenerateRun(
        db=db,
        llm=llm,
        req=body,
        rules=rules,
        catalog=catalog,
        box=box,
        log=RunLog(),
        run=new_run(db, "generate", saved.id if saved else None),
        saved=saved,
    )
    return _stream(db, run.events())


@router.post("/chat", response_class=StreamingResponse, responses=SSE)
def chat(
    body: ChatRequest,
    request: Request,
    db: Db,
    store: RedisStore,
    session: MaybeSession,
    llm: Llm,
) -> StreamingResponse:
    account = _account(db, session)
    _limit(store, request, account, CHAT_PER_ACCOUNT, CHAT_PER_IP)
    saved = _saved_plan(db, account, body.plan_id, body.plan)
    purge_old_history(db)
    run = ChatRun(
        db=db,
        llm=llm,
        req=body,
        show_unpublished=_unpublished(),
        statuses=_statuses(),
        log=RunLog(),
        saved=saved,
        logged_in=account is not None,
    )
    return _stream(db, run.events())


@router.get("/chat/history", response_model=ChatHistory)
def chat_history(
    plan_id: uuid.UUID, db: Db, me: Annotated[m.Account, Depends(current_account)]
) -> ChatHistory:
    try:
        plan = plans_repo.owned_plan(db, me.id, plan_id)
    except plans_repo.PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Plan not found.") from exc
    return history(db, plan)
