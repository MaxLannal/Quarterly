"""The planner agent endpoint (issues #17 and #18): one agent writes the first plan
(`mode="generate"`) and changes it in a chat (`mode="chat"`), streamed as Server-Sent Events.
It replaced the plan generator (`/agents/generate`) and the advisor chat (`/agents/chat`).

Without a configured LLM the planner says so and the student can still plan by hand; typed
confirmations need no model. Logged-out use is allowed (issue #17 D2) and rate-limited by a
Redis-only counter keyed by a hash of the client address and the day (never written to disk);
a logged-in account has its own daily limit. Answering a question continues a run and does not
count as a new generation.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from llm_gateway.api import LLM, get_llm
from planner_core.hashing import plan_hash
from planner_core.models import PlanState
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.agents.planner.chat import PlannerChat, clear_history, history, purge_old_history
from api.agents.planner.harness import PlannerRun
from api.agents.runtime import SSE_HEADERS, RunLog, sse
from api.auth.ratelimit import DAY, Limit, account_subject, ip_subject
from api.auth.sessions import SessionData, current_account, optional_session
from api.auth.store import Store, get_store
from api.config import get_settings
from api.db import models as m
from api.db.session import get_session
from api.repo import catalog as catalog_repo
from api.repo import plans as plans_repo
from api.repo.rules import UnknownProgramsError
from api.schemas.agents import ChatHistory, ErrorEvent
from api.schemas.planner import PlannerEvent, PlannerRequest

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger("api.agents")

Db = Annotated[Session, Depends(get_session)]
Llm = Annotated[LLM, Depends(get_llm)]
MaybeSession = Annotated[SessionData | None, Depends(optional_session)]
RedisStore = Annotated[Store, Depends(get_store)]
Me = Annotated[m.Account, Depends(current_account)]

#: SPEC "A1": 10 generations per account per day; 3 per client address when logged out.
GENERATE_PER_ACCOUNT = Limit("agent-generate:account", 10, DAY)
GENERATE_PER_IP = Limit("agent-generate:ip", 3, DAY)
#: Chat messages per day (docs/OPEN_QUESTIONS.md "Prompt 07").
CHAT_PER_ACCOUNT = Limit("agent-chat:account", 60, DAY)
CHAT_PER_IP = Limit("agent-chat:ip", 30, DAY)

SSE: dict[int | str, dict[str, Any]] = {
    200: {
        "model": PlannerEvent,
        "description": "Server-Sent Events; each `data:` line is one PlannerEvent as JSON.",
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


def _owned(db: Session, account: m.Account, plan_id: uuid.UUID) -> m.Plan:
    try:
        return plans_repo.owned_plan(db, account.id, plan_id)
    except plans_repo.PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Plan not found.") from exc


def _saved_plan(
    db: Session, account: m.Account | None, plan_id: uuid.UUID | None, state: PlanState
) -> m.Plan | None:
    """The account's saved plan, if the request names one and its plan is unchanged since it
    was saved. Another account's plan is a 404."""
    if plan_id is None:
        return None
    if account is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    plan = _owned(db, account, plan_id)
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


@router.post("/planner", response_class=StreamingResponse, responses=SSE)
def planner(
    body: PlannerRequest,
    request: Request,
    db: Db,
    store: RedisStore,
    session: MaybeSession,
    llm: Llm,
) -> StreamingResponse:
    account = _account(db, session)
    saved = _saved_plan(db, account, body.plan_id, body.plan)
    log = RunLog()
    if body.mode == "chat":
        if not (body.message or "").strip():
            raise HTTPException(status_code=422, detail="A chat request needs a message.")
        _limit(store, request, account, CHAT_PER_ACCOUNT, CHAT_PER_IP)
        purge_old_history(db)
        chat = PlannerChat(
            db=db,
            llm=llm,
            req=body,
            show_unpublished=_unpublished(),
            statuses=_statuses(),
            log=log,
            saved=saved,
            account=account,
        )
        return _stream(db, chat.events())
    if body.run_id is None:  # a resume answers a question; it is not a new generation
        _limit(store, request, account, GENERATE_PER_ACCOUNT, GENERATE_PER_IP)
    purge_old_history(db)
    try:
        run = PlannerRun.build(
            db,
            llm,
            body,
            account=account,
            saved=saved,
            show_unpublished=_unpublished(),
            statuses=_statuses(),
            log=log,
        )
    except UnknownProgramsError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unknown program(s): {', '.join(exc.program_ids)}"
        ) from exc
    return _stream(db, run.generate_events())


@router.get("/planner/history", response_model=ChatHistory)
def planner_history(plan_id: uuid.UUID, db: Db, me: Me) -> ChatHistory:
    return history(db, _owned(db, me, plan_id))


@router.delete("/planner/history", status_code=204)
def clear_planner_history(plan_id: uuid.UUID, db: Db, me: Me) -> Response:
    """Clear chat (issue #18): the messages go; open proposals stay on the plan."""
    clear_history(db, _owned(db, me, plan_id))
    db.commit()
    return Response(status_code=204)
