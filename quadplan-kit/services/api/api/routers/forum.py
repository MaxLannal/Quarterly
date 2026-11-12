from typing import Literal

from fastapi import APIRouter, Query, Response

from api.schemas.common import NOT_IMPLEMENTED, Page, not_implemented
from api.schemas.forum import (
    CommentCreate,
    CommentOut,
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

router = APIRouter(prefix="/forum", tags=["forum"], responses=NOT_IMPLEMENTED)


@router.get("/pages", response_model=ForumPageOut)
def find_page(course: str, instructor: str) -> ForumPageOut:
    raise not_implemented("08")


@router.get("/pages/{page_id}", response_model=ForumPageOut)
def get_page(page_id: int) -> ForumPageOut:
    raise not_implemented("08")


@router.get("/pages/{page_id}/posts", response_model=Page[PostOut])
def list_posts(
    page_id: int,
    kind: Literal["review", "discussion"] | None = None,
    sort: Literal["best", "new", "top", "controversial", "hot"] = "best",
    term: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[PostOut]:
    raise not_implemented("08")


@router.post("/pages/{page_id}/posts", response_model=PostOut, status_code=201)
def create_post(page_id: int, body: PostCreate) -> PostOut:
    raise not_implemented("08")


@router.get("/posts/{post_id}", response_model=PostDetail)
def get_post(post_id: int) -> PostDetail:
    raise not_implemented("08")


@router.patch("/posts/{post_id}", response_model=PostOut)
def update_post(post_id: int, body: PostUpdate) -> PostOut:
    raise not_implemented("08")


@router.delete("/posts/{post_id}", status_code=204, response_class=Response)
def delete_post(post_id: int) -> None:
    raise not_implemented("08")


@router.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=201)
def create_comment(post_id: int, body: CommentCreate) -> CommentOut:
    raise not_implemented("08")


@router.post("/votes", response_model=VoteOut)
def vote(body: VoteIn) -> VoteOut:
    raise not_implemented("08")


@router.post("/reports", response_model=ForumReportOut, status_code=202)
def report(body: ForumReportIn) -> ForumReportOut:
    raise not_implemented("08")
