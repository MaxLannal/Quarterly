"""Posts, comments, votes and reports (SPEC "Forum").

Identity: every author, voter and reporter is stored as `author_ref(account_id, page_id)`;
the account id itself never reaches a forum row. "Mine" is decided by recomputing the reader's
ref for the page. Readers see visible items; authors also see their own held or rejected ones,
with the reason.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from api.attributes.records import forget_extractions, forget_summary
from api.auth.hashing import author_ref
from api.db import models as m
from api.forum import moderation, pages
from api.forum.markdown import render_markdown
from api.forum.pseudonyms import DELETED, pseudonym_for
from api.forum.scrub import scrub
from api.forum.sorting import Sort, order_by, wilson_sql
from api.schemas.common import Page
from api.schemas.forum import (
    CommentCreate,
    CommentOut,
    ForumReportIn,
    ForumReportOut,
    PostCreate,
    PostDetail,
    PostOut,
    PostUpdate,
    ReviewRatingIn,
    VoteIn,
    VoteOut,
)

TargetType = Literal["post", "comment"]
REMOVED_BODY = "[removed]"
HELD_BODY = "[awaiting moderation]"


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def not_found(what: str = "Post") -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found.")


def ensure_can_write(account: m.Account) -> None:
    """Suspended or banned accounts can log in and read, but not post, comment or vote."""
    if account.status != "active":
        raise HTTPException(
            status_code=403, detail="Your account cannot post, comment or vote in the forum."
        )
    if account.suspended_until is not None and account.suspended_until > today():
        raise HTTPException(
            status_code=403,
            detail=(
                "Your account is suspended from posting, commenting and voting until "
                f"{account.suspended_until.isoformat()}."
            ),
        )


# --------------------------------------------------------------------------- moderation notes


def _latest_actions(
    db: Session, target_type: TargetType, ids: Iterable[int]
) -> dict[int, m.ModerationAction]:
    ids = list(ids)
    if not ids:
        return {}
    rows = db.scalars(
        sa.select(m.ModerationAction)
        .where(m.ModerationAction.target_type == target_type, m.ModerationAction.target_id.in_(ids))
        .order_by(m.ModerationAction.id)
    )
    return {row.target_id: row for row in rows}


def _open_self_reports(
    db: Session, target_type: TargetType, ids: Iterable[int], ref: str
) -> set[int]:
    ids = list(ids)
    if not ids:
        return set()
    return set(
        db.scalars(
            sa.select(m.Report.target_id).where(
                m.Report.target_type == target_type,
                m.Report.target_id.in_(ids),
                m.Report.reporter_ref == ref,
                m.Report.status == "open",
            )
        )
    )


def author_note(status: str, action: m.ModerationAction | None, appealed: bool) -> str | None:
    if status == "visible":
        return None
    note: str | None
    if action is not None and action.actor == "admin":
        note = "Removed by a moderator." if status == "removed" else "Waiting for a moderator."
    elif action is not None:
        label = action.reason if action.reason in moderation.LABEL_TEXT else None
        note = moderation.decide(label).note if label else None  # type: ignore[arg-type]
        if note is None:
            note = (
                "Held for review: the automatic check is unavailable, so a moderator will read it."
            )
    else:
        note = "Waiting for a moderator." if status == "held" else "Not published."
    if appealed:
        note += " You asked for human review; a moderator will look at it."
    return note


def _notes(
    db: Session, target_type: TargetType, own: dict[int, str], ref: str
) -> dict[int, str | None]:
    """Notes for the reader's own non-visible items (`own`: id -> status)."""
    hidden = [i for i, status in own.items() if status != "visible"]
    actions = _latest_actions(db, target_type, hidden)
    appealed = _open_self_reports(db, target_type, hidden, ref)
    return {i: author_note(own[i], actions.get(i), i in appealed) for i in hidden}


# ------------------------------------------------------------------------------------- votes


def _vote_counts(target_type: TargetType) -> Any:
    return (
        sa.select(
            m.Vote.target_id.label("target_id"),
            sa.func.count().filter(m.Vote.value == 1).label("up"),
            sa.func.count().filter(m.Vote.value == -1).label("down"),
        )
        .where(m.Vote.target_type == target_type)
        .group_by(m.Vote.target_id)
        .subquery()
    )


def _target(db: Session, target_type: TargetType, target_id: int) -> tuple[int, m.Post | m.Comment]:
    """(page id, row) of a post or comment."""
    if target_type == "post":
        post = db.get(m.Post, target_id)
        if post is None:
            raise not_found("Post")
        return post.course_instructor_id, post
    comment = db.get(m.Comment, target_id)
    if comment is None:
        raise not_found("Comment")
    post = db.get(m.Post, comment.post_id)
    assert post is not None  # FK
    return post.course_instructor_id, comment


def vote(db: Session, account: m.Account, body: VoteIn) -> VoteOut:
    page_id, target = _target(db, body.target_type, body.target_id)
    if target.status != "visible":
        # Others' held or removed items do not exist for this reader (no existence leak).
        if target.author_ref != author_ref(account.id, page_id):
            raise not_found("Post" if body.target_type == "post" else "Comment")
        raise HTTPException(status_code=409, detail="You can only vote on published posts.")
    ensure_can_write(account)
    model: type[m.Post] | type[m.Comment] = m.Post if body.target_type == "post" else m.Comment
    # Serialise votes on one item so the tally below counts every committed vote.
    db.execute(sa.select(model.id).where(model.id == target.id).with_for_update())
    ref = author_ref(account.id, page_id)
    where = (
        m.Vote.voter_ref == ref,
        m.Vote.target_type == body.target_type,
        m.Vote.target_id == target.id,
    )
    if body.value == 0:
        db.execute(sa.delete(m.Vote).where(*where))
    else:
        db.execute(
            insert(m.Vote)
            .values(
                voter_ref=ref, target_type=body.target_type, target_id=target.id, value=body.value
            )
            .on_conflict_do_update(
                index_elements=["voter_ref", "target_type", "target_id"],
                set_={"value": body.value},
            )
        )
    total = sa.select(sa.func.coalesce(sa.func.sum(m.Vote.value), 0)).where(
        m.Vote.target_type == body.target_type, m.Vote.target_id == target.id
    )
    score = int(db.scalar(total) or 0)
    db.execute(sa.update(model).where(model.id == target.id).values(score=score))
    db.commit()
    return VoteOut(score=score, my_vote=body.value)


# ------------------------------------------------------------------------------------- posts


@dataclass
class _PostRow:
    post: m.Post
    rating: m.ReviewRating | None
    handle: str | None
    n_comments: int
    my_vote: int


# `review_rating.grade_bucket` is varchar(16); "prefer not to say" (17) is stored as a code.
_GRADE_OUT = {"prefer not to say": "undisclosed"}
_GRADE_IN = {v: k for k, v in _GRADE_OUT.items()}


def _rating_columns(ratings: ReviewRatingIn) -> dict[str, Any]:
    values = ratings.model_dump()
    bucket = values.get("grade_bucket")
    values["grade_bucket"] = _GRADE_OUT.get(bucket, bucket) if bucket else None
    return values


def _ratings_in(rating: m.ReviewRating | None) -> ReviewRatingIn | None:
    if rating is None:
        return None
    bucket = rating.grade_bucket
    return ReviewRatingIn.model_validate(
        {
            "overall": rating.overall,
            "difficulty": rating.difficulty,
            "intellectual_intensity": rating.intellectual_intensity,
            "workload_hours": rating.workload_hours,
            "would_recommend": rating.would_recommend,
            "grade_bucket": _GRADE_IN.get(bucket, bucket) if bucket else None,
        }
    )


def _post_query(ref: str, sort: Sort) -> Any:
    votes = _vote_counts("post")
    comments = (
        sa.select(m.Comment.post_id.label("post_id"), sa.func.count().label("n"))
        .where(m.Comment.status == "visible")
        .group_by(m.Comment.post_id)
        .subquery()
    )
    mine = aliased(m.Vote)
    up = sa.func.coalesce(votes.c.up, 0)
    down = sa.func.coalesce(votes.c.down, 0)
    return (
        sa.select(
            m.Post,
            m.ReviewRating,
            m.Pseudonym.handle,
            sa.func.coalesce(comments.c.n, 0),
            sa.func.coalesce(mine.value, 0),
        )
        .outerjoin(m.ReviewRating, m.ReviewRating.post_id == m.Post.id)
        .outerjoin(m.Pseudonym, m.Pseudonym.id == m.Post.pseudonym_id)
        .outerjoin(votes, votes.c.target_id == m.Post.id)
        .outerjoin(comments, comments.c.post_id == m.Post.id)
        .outerjoin(
            mine,
            sa.and_(mine.target_type == "post", mine.target_id == m.Post.id, mine.voter_ref == ref),
        )
        .order_by(
            *order_by(
                sort,
                up=up,
                down=down,
                score=m.Post.score,
                created_day=m.Post.created_day,
                id_=m.Post.id,
            )
        )
    )


def _visible_or_mine(ref: str) -> Any:
    return sa.or_(m.Post.status == "visible", m.Post.author_ref == ref)


def _rows(db: Session, stmt: Any) -> list[_PostRow]:
    return [
        _PostRow(post, rating, handle, int(n), int(v))
        for post, rating, handle, n, v in db.execute(stmt)
    ]


def _post_outs(db: Session, rows: list[_PostRow], ref: str) -> list[PostOut]:
    own = {r.post.id: r.post.status for r in rows if r.post.author_ref == ref}
    notes = _notes(db, "post", own, ref)
    return [
        PostOut(
            id=r.post.id,
            page_id=r.post.course_instructor_id,
            kind=r.post.kind,
            pseudonym=_handle(r.post.author_ref, r.handle),
            title=r.post.title,
            body_md=r.post.body_md,
            body_html=render_markdown(r.post.body_md),
            term_taken=r.post.term_taken,
            score=r.post.score,
            my_vote=r.my_vote,
            status=r.post.status,
            created_day=r.post.created_day,
            edited_day=r.post.edited_day,
            ratings=_ratings_in(r.rating),
            n_comments=r.n_comments,
            mine=r.post.id in own,
            moderation_note=notes.get(r.post.id),
        )
        for r in rows
    ]


def _handle(ref: str | None, handle: str | None) -> str:
    if ref is None:
        return DELETED
    return handle or "Anonymous"


def list_posts(
    db: Session,
    account: m.Account,
    page_id: int,
    *,
    kind: Literal["review", "discussion"] | None,
    sort: Sort,
    term: str | None,
    limit: int,
    offset: int,
) -> Page[PostOut]:
    page = pages.get_page(db, page_id)
    ref = author_ref(account.id, page.id)
    filters = [m.Post.course_instructor_id == page.id, _visible_or_mine(ref)]
    if kind is not None:
        filters.append(m.Post.kind == kind)
    if term is not None:
        filters.append(m.Post.term_taken == term)
    total = db.scalar(sa.select(sa.func.count()).select_from(m.Post).where(*filters)) or 0
    rows = _rows(db, _post_query(ref, sort).where(*filters).limit(limit).offset(offset))
    return Page[PostOut](items=_post_outs(db, rows, ref), total=total, limit=limit, offset=offset)


def _one_post(db: Session, post_id: int, ref: str) -> PostOut:
    rows = _rows(db, _post_query(ref, "new").where(m.Post.id == post_id))
    return _post_outs(db, rows, ref)[0]


def _check_term(db: Session, page: m.CourseInstructor, term: str) -> None:
    taught = pages.terms_taught(db, page)
    if taught and term not in taught:
        raise HTTPException(
            status_code=422,
            detail="Pick a term in which this instructor taught the course.",
        )


def create_post(db: Session, account: m.Account, page_id: int, body: PostCreate) -> PostOut:
    """Published at once (P08-1): no check before publishing, only the email/phone scrub."""
    page = pages.get_page(db, page_id)
    ensure_can_write(account)
    ref = author_ref(account.id, page.id)
    if body.kind == "review":
        already = db.scalar(
            sa.select(m.Post.id).where(
                m.Post.course_instructor_id == page.id,
                m.Post.author_ref == ref,
                m.Post.kind == "review",
            )
        )
        if already is not None:
            raise HTTPException(
                status_code=409,
                detail="You have already reviewed this course with this instructor. "
                "Edit your review instead.",
            )
    if body.term_taken is not None:
        _check_term(db, page, body.term_taken)
    title = scrub(body.title).strip() or None if body.title else None
    text = scrub(body.body_md)
    pseudonym = pseudonym_for(db, ref, page.id)
    post = m.Post(
        course_instructor_id=page.id,
        kind=body.kind,
        author_ref=ref,
        pseudonym_id=pseudonym.id,
        title=title,
        body_md=text,
        term_taken=body.term_taken,
        status="visible",
    )
    db.add(post)
    try:
        db.flush()
    except IntegrityError as exc:  # a concurrent second review
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already reviewed this page.") from exc
    if body.kind == "review" and body.ratings is not None:
        db.add(m.ReviewRating(post_id=post.id, **_rating_columns(body.ratings)))
    db.commit()
    return _one_post(db, post.id, ref)


def _own_post(db: Session, account: m.Account, post_id: int) -> tuple[m.Post, str]:
    post = db.get(m.Post, post_id)
    if post is None:
        raise not_found()
    ref = author_ref(account.id, post.course_instructor_id)
    if post.author_ref != ref:
        if post.status != "visible":
            raise not_found()
        raise HTTPException(status_code=403, detail="You can only change your own posts.")
    return post, ref


def _removed_by_admin(db: Session, target_type: TargetType, target_id: int) -> bool:
    action = _latest_actions(db, target_type, [target_id]).get(target_id)
    return action is not None and action.actor == "admin" and action.action == "remove"


def update_post(db: Session, account: m.Account, post_id: int, body: PostUpdate) -> PostOut:
    post, ref = _own_post(db, account, post_id)
    if post.status == "removed" and _removed_by_admin(db, "post", post.id):
        raise HTTPException(status_code=409, detail="A moderator removed this post.")
    ensure_can_write(account)
    if post.kind == "discussion" and body.ratings is not None:
        raise HTTPException(status_code=422, detail="A discussion post has no ratings.")
    text_changed = False
    if "title" in body.model_fields_set:
        title = scrub(body.title).strip() or None if body.title else None
        text_changed |= title != post.title
        post.title = title
    if body.body_md is not None:
        text = scrub(body.body_md)
        if not text.strip():
            raise HTTPException(status_code=422, detail="The post is empty.")
        text_changed |= text != post.body_md
        post.body_md = text
    if body.term_taken is not None:
        page = pages.get_page(db, post.course_instructor_id)
        _check_term(db, page, body.term_taken)
        post.term_taken = body.term_taken
    if body.ratings is not None:
        rating = db.get(m.ReviewRating, post.id)
        if rating is None:
            db.add(m.ReviewRating(post_id=post.id, **_rating_columns(body.ratings)))
        else:
            for key, value in _rating_columns(body.ratings).items():
                setattr(rating, key, value)
    if text_changed:
        forget_extractions(db, [post.id])
        forget_summary(db, post.course_instructor_id, post.id)
    post.edited_day = today()
    db.commit()
    return _one_post(db, post.id, ref)


def delete_post(db: Session, account: m.Account, post_id: int) -> None:
    """The author deletes their post. A post with replies is blanked instead, so the
    conversation under it survives."""
    post, _ = _own_post(db, account, post_id)
    if post.status == "removed" and _removed_by_admin(db, "post", post.id):
        # Upheld removals count toward a suspension; deleting must not erase one.
        raise HTTPException(status_code=409, detail="A moderator removed this post.")
    has_comments = db.scalar(sa.select(sa.exists().where(m.Comment.post_id == post.id)))
    forget_extractions(db, [post.id])
    forget_summary(db, post.course_instructor_id, post.id)
    if has_comments:
        db.execute(sa.delete(m.ReviewRating).where(m.ReviewRating.post_id == post.id))
        post.title = None
        post.body_md = "[deleted]"
        post.author_ref = None
        post.pseudonym_id = None
        post.term_taken = None
    else:
        db.execute(
            sa.delete(m.Vote).where(m.Vote.target_type == "post", m.Vote.target_id == post.id)
        )
        db.delete(post)
    db.commit()


# ---------------------------------------------------------------------------------- comments


def _comment_out(
    comment: m.Comment,
    *,
    handle: str | None,
    depth: int,
    my_vote: int,
    mine: bool,
    note: str | None,
    placeholder: bool = False,
) -> CommentOut:
    if placeholder:
        body = REMOVED_BODY if comment.status == "removed" else HELD_BODY
        pseudonym = "[hidden]"
    else:
        body = comment.body_md
        pseudonym = _handle(comment.author_ref, handle)
    return CommentOut(
        id=comment.id,
        post_id=comment.post_id,
        parent_id=comment.parent_id,
        depth=depth,
        pseudonym=pseudonym,
        body_md=body,
        body_html=render_markdown(body),
        score=comment.score,
        my_vote=my_vote,
        status=comment.status,
        created_day=comment.created_day,
        mine=mine,
        moderation_note=note,
    )


def _comments(db: Session, post: m.Post, ref: str) -> list[CommentOut]:
    votes = _vote_counts("comment")
    mine = aliased(m.Vote)
    best = wilson_sql(sa.func.coalesce(votes.c.up, 0), sa.func.coalesce(votes.c.down, 0))
    rows = db.execute(
        sa.select(
            m.Comment,
            m.Pseudonym.handle,
            sa.func.nlevel(m.Comment.path),
            sa.func.coalesce(mine.value, 0),
            best,
        )
        .outerjoin(m.Pseudonym, m.Pseudonym.id == m.Comment.pseudonym_id)
        .outerjoin(votes, votes.c.target_id == m.Comment.id)
        .outerjoin(
            mine,
            sa.and_(
                mine.target_type == "comment",
                mine.target_id == m.Comment.id,
                mine.voter_ref == ref,
            ),
        )
        .where(m.Comment.post_id == post.id)
        .order_by(sa.desc(best), sa.desc(m.Comment.id))
    )
    by_id: dict[int, tuple[m.Comment, str | None, int, int]] = {}
    children: dict[int | None, list[int]] = defaultdict(list)
    for comment, handle, level, my_vote, _ in rows:
        by_id[comment.id] = (comment, handle, int(level) - 1, int(my_vote))
        children[comment.parent_id].append(comment.id)  # already in Best order

    def shown(cid: int) -> bool:
        comment = by_id[cid][0]
        return comment.status == "visible" or comment.author_ref == ref

    keep: dict[int, bool] = {}

    def subtree_has_shown(cid: int) -> bool:
        if cid not in keep:
            keep[cid] = shown(cid) or any(subtree_has_shown(c) for c in children[cid])
        return keep[cid]

    own = {cid: c.status for cid, (c, *_rest) in by_id.items() if c.author_ref == ref}
    notes = _notes(db, "comment", own, ref)
    out: list[CommentOut] = []
    stack = list(reversed(children[None]))
    while stack:
        cid = stack.pop()
        if not subtree_has_shown(cid):
            continue
        comment, handle, depth, my_vote = by_id[cid]
        out.append(
            _comment_out(
                comment,
                handle=handle,
                depth=depth,
                my_vote=my_vote,
                mine=cid in own,
                note=notes.get(cid),
                placeholder=not shown(cid),
            )
        )
        stack.extend(reversed(children[cid]))
    return out


def get_post(db: Session, account: m.Account, post_id: int) -> PostDetail:
    post = db.get(m.Post, post_id)
    if post is None:
        raise not_found()
    ref = author_ref(account.id, post.course_instructor_id)
    if post.status != "visible" and post.author_ref != ref:
        raise not_found()
    out = _one_post(db, post.id, ref)
    return PostDetail(**out.model_dump(), comments=_comments(db, post, ref))


def create_comment(
    db: Session, account: m.Account, post_id: int, body: CommentCreate
) -> CommentOut:
    """Published at once (P08-1), like posts."""
    post = db.get(m.Post, post_id)
    if post is None:
        raise not_found()
    ref = author_ref(account.id, post.course_instructor_id)
    if post.status != "visible":
        if post.author_ref != ref:
            raise not_found()
        raise HTTPException(status_code=409, detail="Replies open once the post is published.")
    parent: m.Comment | None = None
    if body.parent_id is not None:
        parent = db.get(m.Comment, body.parent_id)
        if parent is None or parent.post_id != post.id:
            raise not_found("Comment")
        if parent.status != "visible":
            raise HTTPException(status_code=409, detail="You can only reply to published comments.")
    ensure_can_write(account)
    text = scrub(body.body_md)
    pseudonym = pseudonym_for(db, ref, post.course_instructor_id)
    new_id = int(
        db.scalar(sa.select(sa.func.nextval(sa.func.pg_get_serial_sequence("comment", "id")))) or 0
    )
    path = f"{parent.path}.{new_id}" if parent is not None else str(new_id)
    comment = m.Comment(
        id=new_id,
        post_id=post.id,
        parent_id=parent.id if parent else None,
        path=path,
        author_ref=ref,
        pseudonym_id=pseudonym.id,
        body_md=text,
        status="visible",
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    note = None
    if comment.status != "visible":
        note = _notes(db, "comment", {comment.id: comment.status}, ref)[comment.id]
    return _comment_out(
        comment,
        handle=pseudonym.handle,
        depth=path.count("."),
        my_vote=0,
        mine=True,
        note=note,
    )


# ----------------------------------------------------------------------------------- reports


def report(db: Session, account: m.Account, body: ForumReportIn) -> ForumReportOut:
    page_id, target = _target(db, body.target_type, body.target_id)
    ref = author_ref(account.id, page_id)
    if target.status != "visible" and target.author_ref != ref:
        raise not_found("Post" if body.target_type == "post" else "Comment")
    existing = db.scalar(
        sa.select(m.Report).where(
            m.Report.target_type == body.target_type,
            m.Report.target_id == target.id,
            m.Report.reporter_ref == ref,
            m.Report.status == "open",
        )
    )
    if existing is not None:
        return ForumReportOut(id=existing.id, status="open")
    row = m.Report(
        target_type=body.target_type,
        target_id=target.id,
        reason=scrub(body.reason),
        status="open",
        reporter_ref=ref,
    )
    db.add(row)
    db.commit()
    return ForumReportOut(id=row.id, status="open")


def account_refs(account_id: uuid.UUID, page_ids: Iterable[int]) -> dict[int, str]:
    return {pid: author_ref(account_id, pid) for pid in page_ids}
