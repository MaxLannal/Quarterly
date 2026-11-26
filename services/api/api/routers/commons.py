"""The Commons: course questions with a bot answer and nested replies (`/commons/*`),
docs/BEST-OF-UCHICAGO-PLAN.md.

Reading is public: a logged-out visitor sees every visible question and reply (handles only, like
the rest of the Commons), so a link to a question works for anyone. Writing (asking, replying,
voting, accepting, following, typing, reporting) needs a login and an account allowed to write.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from llm_gateway.api import LLM, get_llm
from sqlalchemy.orm import Session

from api.agents import commons_bot
from api.auth.ratelimit import DAY, HOUR, MINUTE, Limit, account_subject, ip_limit
from api.auth.sessions import SessionData, current_account, optional_session
from api.auth.store import Store, get_store
from api.commons import service
from api.commons.service import Viewer
from api.config import get_settings
from api.db import models as m
from api.db.session import get_session
from api.schemas.commons import (
    CommonsAcceptIn,
    CommonsAcceptOut,
    CommonsBotEvent,
    CommonsBotRequest,
    CommonsFollowIn,
    CommonsFollowOut,
    CommonsPresence,
    CommonsReply,
    CommonsReplyCreate,
    CommonsReplyPosted,
    CommonsReplyUpdate,
    CommonsReportIn,
    CommonsReportOut,
    CommonsThreadCreate,
    CommonsThreadDetail,
    CommonsThreadList,
    CommonsThreadUpdate,
    CommonsVoteIn,
    CommonsVoteOut,
    Sort,
)

# Route functions carry comments, not docstrings: FastAPI copies docstrings into the frozen
# OpenAPI document.


def _private(response: Response) -> None:
    # Answers differ per reader (is_mine, my_vote, following): never let a shared cache keep one.
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(prefix="/commons", tags=["commons"], dependencies=[Depends(_private)])

SessionDep = Annotated[Session, Depends(get_session)]
AccountDep = Annotated[m.Account, Depends(current_account)]
StoreDep = Annotated[Store, Depends(get_store)]
MaybeSession = Annotated[SessionData | None, Depends(optional_session)]
Llm = Annotated[LLM, Depends(get_llm)]


def _viewer(db: SessionDep, session: MaybeSession) -> Viewer:
    account = db.get(m.Account, session.account_id) if session is not None else None
    return Viewer(account)


ViewerDep = Annotated[Viewer, Depends(_viewer)]

# Per-account limits (Redis only, keyed by a hash of the account id). The per-IP limit is loose
# because a campus network shares addresses.
THREADS_PER_HOUR = Limit("commons-thread", 8, HOUR)
THREADS_PER_DAY = Limit("commons-thread-day", 30, DAY)
REPLIES_PER_HOUR = Limit("commons-reply", 60, HOUR)
EDITS_PER_HOUR = Limit("commons-edit", 60, HOUR)
VOTES_PER_HOUR = Limit("commons-vote", 300, HOUR)
REPORTS_PER_DAY = Limit("commons-report", 20, DAY)
TYPING_PER_MINUTE = Limit("commons-typing", 40, MINUTE)
WRITE_IP = Depends(ip_limit("commons-write", 5000))

SSE: dict[int | str, dict[str, Any]] = {
    200: {
        "model": CommonsBotEvent,
        "description": "Server-Sent Events; each `data:` line is one CommonsBotEvent as JSON.",
        "content": {"text/event-stream": {}},
    }
}


@router.get("/threads", response_model=CommonsThreadList)
def list_threads(
    db: SessionDep,
    viewer: ViewerDep,
    sort: Sort = "hot",
    course: Annotated[str | None, Query(max_length=16)] = None,
    subject: Annotated[str | None, Query(max_length=8)] = None,
    tag: Annotated[str | None, Query(max_length=24)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    mine: bool = False,
    cursor: Annotated[str | None, Query(max_length=12)] = None,
    limit: Annotated[int, Query(ge=1, le=30)] = 20,
) -> CommonsThreadList:
    return service.list_threads(
        db,
        viewer,
        sort=sort,
        course=course,
        subject=subject,
        tag=tag,
        q=q,
        mine=mine,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/threads", response_model=CommonsThreadDetail, status_code=201, dependencies=[WRITE_IP]
)
def create_thread(
    db: SessionDep, account: AccountDep, store: StoreDep, body: CommonsThreadCreate
) -> CommonsThreadDetail:
    subject = account_subject(account.id)
    THREADS_PER_HOUR.hit(store, subject)
    THREADS_PER_DAY.hit(store, subject)
    return service.create_thread(db, account, body)


@router.get("/threads/{thread_id}", response_model=CommonsThreadDetail)
def get_thread(db: SessionDep, viewer: ViewerDep, thread_id: int) -> CommonsThreadDetail:
    return service.thread_detail(db, viewer, thread_id)


@router.patch("/threads/{thread_id}", response_model=CommonsThreadDetail, dependencies=[WRITE_IP])
def update_thread(
    db: SessionDep,
    account: AccountDep,
    store: StoreDep,
    thread_id: int,
    body: CommonsThreadUpdate,
) -> CommonsThreadDetail:
    EDITS_PER_HOUR.hit(store, account_subject(account.id))
    return service.update_thread(db, account, thread_id, body)


@router.delete(
    "/threads/{thread_id}", status_code=204, response_class=Response, dependencies=[WRITE_IP]
)
def delete_thread(db: SessionDep, account: AccountDep, store: StoreDep, thread_id: int) -> None:
    EDITS_PER_HOUR.hit(store, account_subject(account.id))
    service.delete_thread(db, account, thread_id)


@router.post(
    "/threads/{thread_id}/replies",
    response_model=CommonsReplyPosted,
    status_code=201,
    dependencies=[WRITE_IP],
)
def create_reply(
    db: SessionDep,
    account: AccountDep,
    store: StoreDep,
    thread_id: int,
    body: CommonsReplyCreate,
) -> CommonsReplyPosted:
    REPLIES_PER_HOUR.hit(store, account_subject(account.id))
    return service.create_reply(db, account, thread_id, body)


@router.patch("/replies/{reply_id}", response_model=CommonsReply, dependencies=[WRITE_IP])
def update_reply(
    db: SessionDep,
    account: AccountDep,
    store: StoreDep,
    reply_id: int,
    body: CommonsReplyUpdate,
) -> CommonsReply:
    EDITS_PER_HOUR.hit(store, account_subject(account.id))
    return service.update_reply(db, account, reply_id, body)


@router.delete(
    "/replies/{reply_id}", status_code=204, response_class=Response, dependencies=[WRITE_IP]
)
def delete_reply(db: SessionDep, account: AccountDep, store: StoreDep, reply_id: int) -> None:
    EDITS_PER_HOUR.hit(store, account_subject(account.id))
    service.delete_reply(db, account, reply_id)


# One vote per reader and item; your own posts cannot be voted on. 0 withdraws a vote.
@router.post("/votes", response_model=CommonsVoteOut, dependencies=[WRITE_IP])
def vote(
    db: SessionDep, account: AccountDep, store: StoreDep, body: CommonsVoteIn
) -> CommonsVoteOut:
    VOTES_PER_HOUR.hit(store, account_subject(account.id))
    return service.vote(db, account, body)


# The asker marks the reply (a person's or the AI's) that answered the question.
@router.post(
    "/threads/{thread_id}/accept", response_model=CommonsAcceptOut, dependencies=[WRITE_IP]
)
def accept(
    db: SessionDep, account: AccountDep, store: StoreDep, thread_id: int, body: CommonsAcceptIn
) -> CommonsAcceptOut:
    EDITS_PER_HOUR.hit(store, account_subject(account.id))
    return service.accept(db, account, thread_id, body.reply_id)


# The AI's answer, streamed: `step` events while it reads the catalog and the forum, then
# `answer` (stored as a bot reply) and `done`. A stored answer is sent back at once. A pending
# question's first answer may be started by anyone who opens it; regenerating (the asker) and
# summoning with @quarterly (reply_to) need a login.
@router.post("/threads/{thread_id}/bot", response_class=StreamingResponse, responses=SSE)
def bot(
    request: Request,
    db: SessionDep,
    viewer: ViewerDep,
    store: StoreDep,
    llm: Llm,
    thread_id: int,
    body: CommonsBotRequest,
) -> StreamingResponse:
    run = commons_bot.prepare(
        db,
        store,
        request,
        viewer,
        thread_id,
        body,
        llm=llm,
        show_unpublished=get_settings().show_unpublished_programs,
    )
    return commons_bot.stream(db, store, run)


# "I am typing a reply": kept 8 seconds in Redis (a hash of the thread ref, nothing else).
@router.post("/threads/{thread_id}/typing", status_code=204, response_class=Response)
def typing(db: SessionDep, account: AccountDep, store: StoreDep, thread_id: int) -> None:
    TYPING_PER_MINUTE.hit(store, account_subject(account.id))
    service.typing(db, store, account, thread_id)


# Cheap live state, polled every few seconds by open pages: how many others are typing, the
# newest reply id, the reply count and the score.
@router.get("/threads/{thread_id}/presence", response_model=CommonsPresence)
def presence(db: SessionDep, viewer: ViewerDep, store: StoreDep, thread_id: int) -> CommonsPresence:
    return service.presence(db, store, viewer, thread_id)


# Follow a question (stored in the profile). The update alerts that listed its new replies went
# with GET /me/updates (OPEN_QUESTIONS M21-2).
@router.post(
    "/threads/{thread_id}/follow", response_model=CommonsFollowOut, dependencies=[WRITE_IP]
)
def follow(
    db: SessionDep, account: AccountDep, thread_id: int, body: CommonsFollowIn
) -> CommonsFollowOut:
    return service.follow(db, account, thread_id, body.follow)


@router.post("/reports", response_model=CommonsReportOut, status_code=202, dependencies=[WRITE_IP])
def report(
    db: SessionDep, account: AccountDep, store: StoreDep, body: CommonsReportIn
) -> CommonsReportOut:
    REPORTS_PER_DAY.hit(store, account_subject(account.id))
    return service.report(db, account, body)
