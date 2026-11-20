"""The feed (`/feed`, `/feed/categories`, `/agents/feed-notes`), docs/BEST-OF-UCHICAGO-PLAN.md.

Public endpoints: logged out, the feed is a curated mix and the notes are written for "anon";
logged in, both read the student's profile and routes. Forum posts (which need a login to read)
appear only for a logged-in reader; Commons replies and questions are public.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from llm_gateway.api import LLM, get_llm
from sqlalchemy.orm import Session

from api.auth.sessions import SessionData, optional_session
from api.auth.store import Store, get_store
from api.db.session import get_session
from api.feed import notes as feed_notes
from api.feed import service
from api.schemas.feed import FeedCategories, FeedNotes, FeedNotesRequest, FeedPage, FeedTab

router = APIRouter(tags=["feed"])

Db = Annotated[Session, Depends(get_session)]
MaybeSession = Annotated[SessionData | None, Depends(optional_session)]
RedisStore = Annotated[Store, Depends(get_store)]
Llm = Annotated[LLM, Depends(get_llm)]


@router.get("/feed", response_model=FeedPage)
def get_feed(
    db: Db,
    session: MaybeSession,
    tab: FeedTab = "for_you",
    categories: Annotated[
        str | None,
        Query(
            max_length=400,
            description="Comma-separated category keys; absent = the profile's saved focus.",
        ),
    ] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=service.PAGE_MAX)] = service.PAGE_DEFAULT,
) -> FeedPage:
    # The feed's items for one page; `next_cursor` continues the same stream.
    account_id = session.account_id if session is not None else None
    return service.build_feed(
        db, account_id, tab=tab, categories=categories, cursor=cursor, limit=limit
    )


@router.get("/feed/categories", response_model=FeedCategories)
def get_categories(db: Db, session: MaybeSession) -> FeedCategories:
    # The categories (subject families) a student can focus on, with the saved choice.
    return service.list_categories(db, session.account_id if session is not None else None)


@router.post("/agents/feed-notes", response_model=FeedNotes)
def post_feed_notes(
    body: FeedNotesRequest,
    request: Request,
    db: Db,
    store: RedisStore,
    session: MaybeSession,
    llm: Llm,
) -> FeedNotes:
    # One AI line per visible item and a headline (cached for the day); deterministic reasons
    # when the AI is off, unavailable or over its daily limit.
    return feed_notes.feed_notes(
        db,
        store,
        llm,
        request,
        session.account_id if session is not None else None,
        body.item_ids,
        tab=body.tab,
        categories=body.categories,
    )
