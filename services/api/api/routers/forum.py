from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from api.auth.ratelimit import DAY, HOUR, Limit, account_subject, ip_limit
from api.auth.sessions import SessionData, current_account, optional_session
from api.auth.store import Store, get_store
from api.commons.service import Viewer
from api.config import get_settings
from api.db.models import Account
from api.db.session import get_session
from api.forum import board, pages, service, stats
from api.repo import catalog as catalog_repo
from api.schemas.board import ForumItemList, ForumStats, ItemType, Period
from api.schemas.common import Page
from api.schemas.forum import (
    CommentCreate,
    CommentOut,
    CourseForumOut,
    ForumPageOut,
    ForumReportIn,
    ForumReportOut,
    PostCreate,
    PostDetail,
    PostOut,
    PostUpdate,
    VoteIn,
    VoteOut,
)

# Route functions carry comments, not docstrings: FastAPI copies docstrings into the frozen
# OpenAPI document. Every forum route needs a login (SPEC sitemap), except the `/forum` page's
# list (`GET /forum/items`), which shows a logged-out reader the public Commons discussions only.


def _private(response: Response) -> None:
    # Forum content is for logged-in readers only: never let a shared cache keep it.
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(prefix="/forum", tags=["forum"], dependencies=[Depends(_private)])

SessionDep = Annotated[Session, Depends(get_session)]
AccountDep = Annotated[Account, Depends(current_account)]
StoreDep = Annotated[Store, Depends(get_store)]
MaybeSession = Annotated[SessionData | None, Depends(optional_session)]

# Per-account limits (Redis only, keyed by a hash of the account id). The per-IP limits on
# the routes are loose, because a campus network shares addresses.
POSTS_PER_HOUR = Limit("forum-post", 10, HOUR)
POSTS_PER_DAY = Limit("forum-post-day", 30, DAY)
EDITS_PER_HOUR = Limit("forum-edit", 30, HOUR)
COMMENTS_PER_HOUR = Limit("forum-comment", 60, HOUR)
VOTES_PER_HOUR = Limit("forum-vote", 300, HOUR)
REPORTS_PER_DAY = Limit("forum-report", 20, DAY)
WRITE_IP = Depends(ip_limit("forum-write", 5000))


@contextmanager
def _not_found() -> Iterator[None]:
    try:
        yield
    except pages.PageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# The `/forum` page's list (issue #20): course reviews and Commons discussions, newest first.
# Reviews only for logged-in readers; `tag` and `mine` are Commons filters (reviews left out);
# `instructor` leaves discussions out.
@router.get("/items", response_model=ForumItemList)
def list_items(
    db: SessionDep,
    session: MaybeSession,
    item_type: Annotated[ItemType | None, Query(alias="type")] = None,
    course: Annotated[str | None, Query(max_length=16)] = None,
    instructor: Annotated[str | None, Query(max_length=128)] = None,
    subject: Annotated[str | None, Query(max_length=8)] = None,
    tag: Annotated[str | None, Query(max_length=24)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    mine: bool = False,
    cursor: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=30)] = 20,
) -> ForumItemList:
    account = db.get(Account, session.account_id) if session is not None else None
    return board.list_items(
        db,
        Viewer(account),
        item_type=item_type,
        course=course,
        instructor=instructor,
        subject=subject,
        tag=tag,
        q=q,
        mine=mine,
        cursor=cursor,
        limit=limit,
    )


# Ratings statistics and rankings for the `/forum` page (issue #20): Bayesian averages of the
# overall rating (k = 5), subjects with at least 3 reviews, over the last quarter or year.
@router.get("/stats", response_model=ForumStats)
def forum_stats(db: SessionDep, _: AccountDep, period: Period = "quarter") -> ForumStats:
    statuses = (
        catalog_repo.ALL_STATUSES
        if get_settings().show_unpublished_programs
        else catalog_repo.PUBLISHED
    )
    return stats.cached_stats(db, period, statuses=statuses)


@router.get("/pages", response_model=ForumPageOut)
def find_page(db: SessionDep, _: AccountDep, course: str, instructor: str) -> ForumPageOut:
    with _not_found():
        return pages.page_out(db, pages.find_page(db, course, instructor))


@router.get("/pages/{page_id}", response_model=ForumPageOut)
def get_page(db: SessionDep, _: AccountDep, page_id: int) -> ForumPageOut:
    with _not_found():
        return pages.cached_page_out(db, page_id)


# Course-level view: every instructor's page of one course, ratings pooled.
@router.get("/courses/{code}", response_model=CourseForumOut)
def course_forum(db: SessionDep, _: AccountDep, code: str) -> CourseForumOut:
    with _not_found():
        return pages.course_forum(db, code)


@router.get("/pages/{page_id}/posts", response_model=Page[PostOut])
def list_posts(
    db: SessionDep,
    account: AccountDep,
    page_id: int,
    kind: Literal["review", "discussion"] | None = None,
    sort: Literal["best", "new", "top", "controversial", "hot"] = "best",
    term: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[PostOut]:
    with _not_found():
        return service.list_posts(
            db, account, page_id, kind=kind, sort=sort, term=term, limit=limit, offset=offset
        )


@router.post(
    "/pages/{page_id}/posts", response_model=PostOut, status_code=201, dependencies=[WRITE_IP]
)
def create_post(
    db: SessionDep,
    account: AccountDep,
    store: StoreDep,
    page_id: int,
    body: PostCreate,
) -> PostOut:
    subject = account_subject(account.id)
    POSTS_PER_HOUR.hit(store, subject)
    POSTS_PER_DAY.hit(store, subject)
    with _not_found():
        return service.create_post(db, account, page_id, body)


@router.get("/posts/{post_id}", response_model=PostDetail)
def get_post(db: SessionDep, account: AccountDep, post_id: int) -> PostDetail:
    return service.get_post(db, account, post_id)


@router.patch("/posts/{post_id}", response_model=PostOut, dependencies=[WRITE_IP])
def update_post(
    db: SessionDep,
    account: AccountDep,
    store: StoreDep,
    post_id: int,
    body: PostUpdate,
) -> PostOut:
    EDITS_PER_HOUR.hit(store, account_subject(account.id))
    with _not_found():
        return service.update_post(db, account, post_id, body)


@router.delete(
    "/posts/{post_id}", status_code=204, response_class=Response, dependencies=[WRITE_IP]
)
def delete_post(db: SessionDep, account: AccountDep, store: StoreDep, post_id: int) -> None:
    EDITS_PER_HOUR.hit(store, account_subject(account.id))
    service.delete_post(db, account, post_id)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentOut,
    status_code=201,
    dependencies=[WRITE_IP],
)
def create_comment(
    db: SessionDep,
    account: AccountDep,
    store: StoreDep,
    post_id: int,
    body: CommentCreate,
) -> CommentOut:
    COMMENTS_PER_HOUR.hit(store, account_subject(account.id))
    return service.create_comment(db, account, post_id, body)


@router.post("/votes", response_model=VoteOut, dependencies=[WRITE_IP])
def vote(db: SessionDep, account: AccountDep, store: StoreDep, body: VoteIn) -> VoteOut:
    VOTES_PER_HOUR.hit(store, account_subject(account.id))
    return service.vote(db, account, body)


# Report a post or comment. Reporting your own held or rejected post asks for human review.
@router.post("/reports", response_model=ForumReportOut, status_code=202, dependencies=[WRITE_IP])
def report(
    db: SessionDep, account: AccountDep, store: StoreDep, body: ForumReportIn
) -> ForumReportOut:
    REPORTS_PER_DAY.hit(store, account_subject(account.id))
    return service.report(db, account, body)
