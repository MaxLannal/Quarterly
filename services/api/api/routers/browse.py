"""The Catalog page's browse rows and the course rating summaries (issue #19).

- `GET /catalog/browse`: public. Logged out, the spotlights are a curated mix and the quotes are
  Commons replies only; logged in, the spotlights follow the student's profile and the quotes
  also hold forum reviews and discussions (the forum needs a login to read).
- `GET /course-ratings?codes=A,B`: logged in only, like the ratings on the course page.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth.sessions import SessionData, current_account, optional_session
from api.db import models as m
from api.db.session import get_session
from api.feed import service
from api.feed.new_courses import new_courses
from api.forum.pages import pages_of_code, pooled_ratings
from api.repo import catalog as catalog_repo
from api.schemas.browse import CatalogBrowse, CourseRatings
from api.schemas.common import ErrorOut

router = APIRouter(tags=["catalog"])

Db = Annotated[Session, Depends(get_session)]
MaybeSession = Annotated[SessionData | None, Depends(optional_session)]
Me = Annotated[m.Account, Depends(current_account)]

#: The most codes one ratings request may ask for (a page of results plus the browse rows).
MAX_CODES = 60
AUTH: dict[int | str, dict[str, Any]] = {401: {"model": ErrorOut, "description": "Not logged in"}}


@router.get("/catalog/browse", response_model=CatalogBrowse)
def browse(db: Db, session: MaybeSession) -> CatalogBrowse:
    # The rows shown before the student searches: new courses, spotlights, student quotes.
    account_id = session.account_id if session is not None else None
    spotlights, quotes = service.browse_rows(db, account_id)
    return CatalogBrowse(
        catalog_year=catalog_repo.latest_catalog_year(db),
        new_courses=new_courses(db),
        spotlights=spotlights,
        quotes=quotes,
    )


@router.get("/course-ratings", response_model=CourseRatings, responses=AUTH)
def course_ratings(
    db: Db,
    _: Me,
    codes: Annotated[str, Query(max_length=1200, description="Comma-separated course codes")],
) -> CourseRatings:
    # Student ratings pooled over every instructor's page of each course (logged in only).
    wanted: list[str] = []
    for raw in codes.split(","):
        code = catalog_repo.normalize_code(raw)
        if code and code not in wanted:
            wanted.append(code)
    out = {}
    for code in wanted[:MAX_CODES]:
        pages = pages_of_code(db, code)
        out[code] = pooled_ratings(db, [p.id for p, _ in pages])
    return CourseRatings(ratings=out)
