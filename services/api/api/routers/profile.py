"""The personal dashboard: profile and the interviewing guide (`/me/profile`,
`/agents/interview`), docs/BEST-OF-UCHICAGO-PLAN.md. The routes (`/me/routes`,
`/agents/routes`) were removed in issue #15.

Everything here needs a logged-in account (401 otherwise). The guide only reads: it proposes
profile facts, and the browser saves what the student keeps (PATCH /me/profile)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse, StreamingResponse
from llm_gateway.api import LLM, get_llm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api import profile_data as data
from api.agents.interview import InterviewRun, welcome_cached
from api.agents.runtime import SSE_HEADERS, sse
from api.auth.ratelimit import DAY, Limit, account_subject
from api.auth.sessions import current_account
from api.auth.store import Store, get_store
from api.config import get_settings
from api.db import models as m
from api.db.session import get_session
from api.profile_questions import QuestionSet, question_set
from api.schemas.agents import ErrorEvent
from api.schemas.common import ErrorOut
from api.schemas.profile import (
    InterviewEvent,
    InterviewRequest,
    ProfileOut,
    ProfilePatch,
    ProfileProposalCreate,
    ProfileProposalOut,
)

router = APIRouter(tags=["profile"])
logger = logging.getLogger("api.profile")

Db = Annotated[Session, Depends(get_session)]
Me = Annotated[m.Account, Depends(current_account)]
Llm = Annotated[LLM, Depends(get_llm)]
RedisStore = Annotated[Store, Depends(get_store)]

#: Model turns of the guide per account per day; beyond it the deterministic guide answers.
INTERVIEW_PER_ACCOUNT = Limit("agent-interview:account", 150, DAY)

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


@router.get("/profile/questions", response_model=QuestionSet)
def get_questions(response: Response) -> QuestionSet:
    # The General Information questions (data/profile/questions.yaml): the registration form,
    # the dashboard and the dashboard agent's answer boxes read them. Public: no student data.
    response.headers["Cache-Control"] = "public, max-age=300"
    return question_set()


@router.get("/me/profile", response_model=ProfileOut, responses=AUTH)
def get_profile(db: Db, me: Me, response: Response) -> ProfileOut:
    # The row is created on first read; the email comes from the account each time.
    row = data.ensure_profile(db, me.id)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return data.profile_out(db, me, row)


@router.get(
    "/me/profile/export.md",
    response_class=PlainTextResponse,
    responses={**AUTH, 200: {"content": {"text/markdown": {}}, "description": "student.md"}},
)
def export_student_md(db: Db, me: Me) -> PlainTextResponse:
    # student.md with the working information (Issue #14): everything Quarterly keeps about the
    # student's plans, without the email or the username.
    row = data.ensure_profile(db, me.id)
    db.commit()
    return PlainTextResponse(
        data.render_student_md(db, row, working_notes=True),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="student.md"',
            "Cache-Control": "no-store",
        },
    )


@router.patch(
    "/me/profile",
    response_model=ProfileOut,
    responses={**AUTH, 422: {"model": ErrorOut, "description": "Unknown program or course"}},
)
def patch_profile(body: ProfilePatch, db: Db, me: Me, response: Response) -> ProfileOut:
    # A partial update: only the fields sent change (the registration form, the dashboard, the
    # dashboard agent's accepted answers and the Commons follow button send some of them).
    row = data.ensure_profile(db, me.id)
    try:
        data.apply_patch(db, row, body)
    except data.UnknownProgramError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422, detail=f"Unknown program(s): {', '.join(exc.program_ids)}"
        ) from exc
    except data.UnknownCourseError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422, detail=f"Unknown course(s): {', '.join(exc.codes)}"
        ) from exc
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return data.profile_out(db, me, row)


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


# ------------------------------------------------------------------------------ proposals


def _proposal_out(row: m.ProfileProposal) -> ProfileProposalOut:
    return ProfileProposalOut(
        id=str(row.id),
        field=row.field,
        value=row.value,
        source=row.source,
        status=row.status,
        created_day=row.created_day,
    )


def _patch_for(field: str, value: Any) -> ProfilePatch:
    """The answer as a record patch: only fields of the question file, checked like a PATCH."""
    fields = {q.field for q in question_set().questions if q.type != "table"}
    if field not in fields:
        raise HTTPException(status_code=422, detail=f"Unknown field: {field}")
    try:
        return ProfilePatch.model_validate({field: value})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Not a valid answer for {field}.") from exc


def _own_proposal(db: Session, me: m.Account, proposal_id: uuid.UUID) -> m.ProfileProposal:
    row = db.get(m.ProfileProposal, proposal_id)
    if row is None or row.account_id != me.id:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    if row.status != "proposed":
        raise HTTPException(status_code=409, detail=f"This answer is {row.status}.")
    return row


@router.get("/me/profile/proposals", response_model=list[ProfileProposalOut], responses=AUTH)
def list_profile_proposals(db: Db, me: Me) -> list[ProfileProposalOut]:
    rows = db.scalars(
        sa.select(m.ProfileProposal)
        .where(m.ProfileProposal.account_id == me.id, m.ProfileProposal.status == "proposed")
        .order_by(m.ProfileProposal.created_day, m.ProfileProposal.field)
    ).all()
    return [_proposal_out(r) for r in rows]


@router.post(
    "/me/profile/proposals", response_model=ProfileProposalOut, status_code=201, responses=AUTH
)
def create_profile_proposal(body: ProfileProposalCreate, db: Db, me: Me) -> ProfileProposalOut:
    _patch_for(body.field, body.value)
    row = m.ProfileProposal(
        account_id=me.id,
        field=body.field,
        value=body.value,
        source="import",
        status="proposed",
        created_day=data.today(),
    )
    db.add(row)
    db.commit()
    return _proposal_out(row)


@router.post(
    "/me/profile/proposals/{proposal_id}/accept", response_model=ProfileOut, responses=AUTH
)
def accept_profile_proposal(proposal_id: uuid.UUID, db: Db, me: Me) -> ProfileOut:
    row = _own_proposal(db, me, proposal_id)
    patch = _patch_for(row.field, row.value)
    profile = data.ensure_profile(db, me.id)
    try:
        data.apply_patch(db, profile, patch)
    except (data.UnknownProgramError, data.UnknownCourseError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail="This answer no longer fits.") from exc
    row.status = "accepted"
    db.commit()
    return data.profile_out(db, me, profile)


@router.post("/me/profile/proposals/{proposal_id}/reject", status_code=204, responses=AUTH)
def reject_profile_proposal(proposal_id: uuid.UUID, db: Db, me: Me) -> Response:
    _own_proposal(db, me, proposal_id).status = "rejected"
    db.commit()
    return Response(status_code=204)
