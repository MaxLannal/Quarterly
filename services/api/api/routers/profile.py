"""The personal dashboard: profile, the interviewing guide and routes (`/me/profile`,
`/me/routes`, `/agents/interview`, `/agents/routes`), docs/BEST-OF-UCHICAGO-PLAN.md.

Everything here needs a logged-in account (401 otherwise). The agents only read: the guide
proposes profile facts and the drafter proposes routes; the browser saves what the student
keeps (PATCH /me/profile, POST /me/routes)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from llm_gateway.api import LLM, get_llm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api import profile_data as data
from api.agents.interview import InterviewRun, welcome_cached
from api.agents.routes import RoutesRun
from api.agents.runtime import SSE_HEADERS, sse
from api.auth.ratelimit import DAY, Limit, account_subject
from api.auth.sessions import current_account
from api.auth.store import Store, get_store
from api.config import get_settings
from api.db import models as m
from api.db.session import get_session
from api.schemas.agents import ErrorEvent
from api.schemas.common import ErrorOut
from api.schemas.profile import (
    InterviewEvent,
    InterviewRequest,
    ProfileOut,
    ProfilePatch,
    RouteIn,
    RouteList,
    RouteOut,
    RoutePatch,
    RoutesEvent,
    RoutesRequest,
)

router = APIRouter(tags=["profile"])
logger = logging.getLogger("api.profile")

Db = Annotated[Session, Depends(get_session)]
Me = Annotated[m.Account, Depends(current_account)]
Llm = Annotated[LLM, Depends(get_llm)]
RedisStore = Annotated[Store, Depends(get_store)]

#: Model turns of the guide per account per day; beyond it the deterministic guide answers.
INTERVIEW_PER_ACCOUNT = Limit("agent-interview:account", 150, DAY)
#: Route drafts per account per day; beyond it the routes are assembled by rules.
ROUTES_PER_ACCOUNT = Limit("agent-routes:account", 12, DAY)

AUTH: dict[int | str, dict[str, Any]] = {401: {"model": ErrorOut, "description": "Not logged in"}}
FAILED = "Something went wrong on our side. Try again."


def _sse(model: type[BaseModel], what: str) -> dict[int | str, dict[str, Any]]:
    return {
        **AUTH,
        200: {
            "model": model,
            "description": f"Server-Sent Events; each `data:` line is one {what} as JSON.",
            "content": {"text/event-stream": {}},
        },
    }


def _unpublished() -> bool:
    return get_settings().show_unpublished_programs


def _within(store: Store, limit: Limit, account: m.Account) -> bool:
    """Count one model run; False once the daily limit is used up (the rules answer then)."""
    try:
        limit.hit(store, account_subject(account.id))
    except HTTPException:
        return False
    return True


def _stream(db: Session, events: Iterator[BaseModel]) -> StreamingResponse:
    def body() -> Iterator[str]:
        try:
            for event in events:
                yield sse(event)
        except Exception:
            logger.exception("dashboard agent run failed")  # no request data in the message
            db.rollback()
            yield sse(ErrorEvent(message=FAILED))

    return StreamingResponse(body(), media_type="text/event-stream", headers=SSE_HEADERS)


# ------------------------------------------------------------------------------ profile


@router.get("/me/profile", response_model=ProfileOut, responses=AUTH)
def get_profile(db: Db, me: Me, response: Response) -> ProfileOut:
    # The row is created on first read; the email comes from the account each time.
    row = data.ensure_profile(db, me.id)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return data.profile_out(db, me, row)


@router.patch(
    "/me/profile",
    response_model=ProfileOut,
    responses={**AUTH, 422: {"model": ErrorOut, "description": "Unknown program"}},
)
def patch_profile(body: ProfilePatch, db: Db, me: Me, response: Response) -> ProfileOut:
    # A partial update: only the fields sent change (the feed, the Commons and the companion
    # send some of them too).
    row = data.ensure_profile(db, me.id)
    try:
        data.apply_patch(db, row, body)
    except data.UnknownProgramError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422, detail=f"Unknown program(s): {', '.join(exc.program_ids)}"
        ) from exc
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return data.profile_out(db, me, row)


# ------------------------------------------------------------------------------ routes


def _owned(db: Session, me: m.Account, route_id: uuid.UUID) -> m.Pathway:
    try:
        return data.owned_route(db, me.id, route_id)
    except data.RouteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Route not found.") from exc


@router.get("/me/routes", response_model=RouteList, responses=AUTH)
def list_routes(db: Db, me: Me) -> RouteList:
    return data.list_routes(db, me.id)


@router.post(
    "/me/routes",
    response_model=RouteOut,
    status_code=201,
    responses={**AUTH, 409: {"model": ErrorOut, "description": "Too many routes"}},
)
def create_route(body: RouteIn, db: Db, me: Me) -> RouteOut:
    # Unknown course codes and program ids are dropped; titles come from the catalog.
    try:
        row = data.create_route(db, me.id, body)
    except data.RouteLimitError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"You can keep up to {data.MAX_ROUTES} routes. Delete one to keep another.",
        ) from exc
    db.commit()
    return data.route_out(db, row)


@router.patch(
    "/me/routes/{route_id}",
    response_model=RouteOut,
    responses={**AUTH, 404: {"model": ErrorOut, "description": "Not found"}},
)
def patch_route(route_id: uuid.UUID, body: RoutePatch, db: Db, me: Me) -> RouteOut:
    # status "chosen" moves any other chosen route back to "open" in the same transaction.
    row = _owned(db, me, route_id)
    data.patch_route(db, row, body)
    db.commit()
    db.refresh(row)
    return data.route_out(db, row)


@router.delete(
    "/me/routes/{route_id}",
    status_code=204,
    response_class=Response,
    responses={**AUTH, 404: {"model": ErrorOut, "description": "Not found"}},
)
def delete_route(route_id: uuid.UUID, db: Db, me: Me) -> None:
    row = _owned(db, me, route_id)
    db.delete(row)
    db.commit()


# ------------------------------------------------------------------------------ agents


@router.post(
    "/agents/interview",
    response_class=StreamingResponse,
    responses=_sse(InterviewEvent, "InterviewEvent"),
    tags=["agents"],
)
def interview(
    body: InterviewRequest, db: Db, me: Me, store: RedisStore, llm: Llm
) -> StreamingResponse:
    # The guide's next turn. It proposes facts; the browser PATCHes what the student keeps.
    row = data.ensure_profile(db, me.id)
    db.commit()
    cached = body.mode == "welcome_back" and welcome_cached(store, me, row)
    run = InterviewRun(
        db=db,
        llm=llm,
        account=me,
        row=row,
        req=body,
        store=store,
        show_unpublished=_unpublished(),
        # A cached welcome-back greeting costs nothing, so it is not counted.
        use_ai=cached or _within(store, INTERVIEW_PER_ACCOUNT, me),
    )
    return _stream(db, run.events())


@router.post(
    "/agents/routes",
    response_class=StreamingResponse,
    responses=_sse(RoutesEvent, "RoutesEvent"),
    tags=["agents"],
)
def draft_routes(
    body: RoutesRequest, db: Db, me: Me, llm: Llm, store: RedisStore
) -> StreamingResponse:
    # Drafts only: nothing is saved until the student keeps a route (POST /me/routes).
    row = data.ensure_profile(db, me.id)
    db.commit()
    run = RoutesRun(
        db=db,
        llm=llm,
        account=me,
        row=row,
        req=body,
        show_unpublished=_unpublished(),
        use_ai=_within(store, ROUTES_PER_ACCOUNT, me),
    )
    return _stream(db, run.events())
