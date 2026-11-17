"""The nightly forum -> attributes job (prompt 11). Order:

1. Cold-start estimates for courses that have a forum page and no estimate yet (A3, Sonnet).
2. Text extraction for visible posts not yet extracted, or edited since (A3, Haiku); one
   `extraction_run` row per post and text version records what was accepted. Only discussion
   posts give text values (a review's own ratings already count), at most one per post and key.
3. The numeric update (`aggregate`) for every course with a forum page and every page.
4. "What students say" for pages with 3 new visible posts since the last summary, a summary
   older than 30 days, or a summary citing a post that is no longer visible (A3, Sonnet),
   published only after the code checks and A4 moderation.

Without a model (`LLMUnavailableError`, e.g. while real calls are on hold) steps 1, 2 and 4 are
skipped and step 3 runs on the structured ratings alone. Writes go to `attribute_value`
(one row per subject and key, replaced each night) and `forum_summary`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from llm_gateway.api import LLM, LLMUnavailableError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.attributes import a3
from api.attributes.aggregate import (
    FORUM_KEYS,
    K_ESTIMATE,
    MIN_N,
    Prior,
    Rating,
    count_posts,
    department_prior,
    posterior,
    rating_weight,
)
from api.attributes.records import forget_extractions, hidden_citations
from api.db import models as m
from api.forum.pages import crosslisted_codes

log = logging.getLogger("api.attributes")

DEFINITIONS = {
    "workload_hours": ("hours per week outside class", "Weekly workload outside class"),
    "difficulty": ("1-5", "How hard the course is"),
    "intellectual_intensity": ("1-5", "How intellectually demanding the course is"),
    "pace": ("1-5", "How fast the course moves"),
    "grading_strictness": ("1-5", "How strictly the course is graded"),
    "recommend_rate": ("0-1", "Share of reviewers who would recommend it"),
}
REBUILD_AFTER_POSTS = 3
REBUILD_AFTER_DAYS = 30
COLD_START_PER_RUN = 200
EXTRACT_PER_RUN = 500


@dataclass
class Stats:
    cold_start: int = 0
    extracted: int = 0
    attributes: int = 0
    summaries: int = 0
    rejected: list[str] = field(default_factory=list)
    llm_available: bool = True


def _upsert_attribute(
    db: Session, subject_type: str, subject_id: str, key: str, values: dict[str, Any]
) -> None:
    stmt = insert(m.AttributeValue).values(
        subject_type=subject_type, subject_id=subject_id, key=key, **values
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["subject_type", "subject_id", "key"],
            set_={k: stmt.excluded[k] for k in (*values, "computed_at")},
        )
    )


def _definitions(db: Session) -> None:
    for key, (scale, description) in DEFINITIONS.items():
        db.execute(
            insert(m.AttributeDef)
            .values(key=key, scale=scale, description=description)
            .on_conflict_do_nothing()
        )


def _estimates(db: Session) -> dict[str, dict[str, float]]:
    """Course code -> {key: estimate}, from the stored cold-start rows."""
    out: dict[str, dict[str, float]] = defaultdict(dict)
    rows = db.scalars(sa.select(m.AttributeValue).where(m.AttributeValue.subject_type == "course"))
    for row in rows:
        estimate = (row.evidence or {}).get("estimate")
        if isinstance(estimate, int | float):
            out[row.subject_id][row.key] = float(estimate)
    return out


def _cold_start(db: Session, llm: LLM, stats: Stats) -> None:
    have = _estimates(db)
    courses = db.execute(
        sa.select(m.Course.code, m.Course.title, m.Course.description)
        .join(m.CourseInstructor, m.CourseInstructor.course_id == m.Course.id)
        .distinct()
        .order_by(m.Course.code)
    ).all()
    for code, title, description in courses:
        if stats.cold_start >= COLD_START_PER_RUN or not stats.llm_available:
            return
        if "workload_hours" in have.get(code, {}):
            continue
        try:
            guess = a3.cold_start(llm, code, title, description)
        except LLMUnavailableError:
            stats.llm_available = False
            return
        except Exception as exc:  # a malformed answer: skip this course tonight
            stats.rejected.append(f"cold start {code}: {type(exc).__name__}")
            continue
        for key, value in (
            ("workload_hours", guess.workload_hours),
            ("difficulty", guess.difficulty),
        ):
            _upsert_attribute(
                db,
                "course",
                code,
                key,
                {
                    "value": value,
                    "ci_low": None,
                    "ci_high": None,
                    "n": 0,
                    "method": "prior",
                    "evidence": {
                        "estimate": value,
                        "reason": guess.reason,
                        "task": "a3_cold_start_estimate",
                    },
                },
            )
        stats.cold_start += 1


def _text(title: str | None, body: str) -> str:
    return f"{title or ''}\n{body}"


def _version(text: str) -> str:
    """Identifies a post's text, so an edited post is extracted again."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _extracted(db: Session) -> dict[int, dict[str, Any]]:
    """Post id -> its latest extraction (its `text_version` says which text it read)."""
    out: dict[int, dict[str, Any]] = {}
    for run in db.scalars(
        sa.select(m.ExtractionRun)
        .where(m.ExtractionRun.kind == "a3_extraction")
        .order_by(m.ExtractionRun.id)
    ):
        pid = (run.output or {}).get("post_id")
        if isinstance(pid, int):
            out[pid] = run.output or {}
    return out


def _extract(db: Session, llm: LLM, stats: Stats) -> None:
    done = {pid: out.get("text_version") for pid, out in _extracted(db).items()}
    posts = db.execute(
        sa.select(m.Post.id, m.Post.title, m.Post.body_md)
        .outerjoin(m.ReviewRating, m.ReviewRating.post_id == m.Post.id)
        .where(m.Post.status == "visible", m.ReviewRating.post_id.is_(None))
        .order_by(m.Post.id)
    ).all()
    for post_id, title, body in posts:
        if stats.extracted >= EXTRACT_PER_RUN or not stats.llm_available:
            return
        text = _text(title, body)
        if done.get(post_id) == _version(text):
            continue
        try:
            found = a3.extract(llm, post_id, text)
            forget_extractions(db, [post_id])  # the earlier text's quotes
        except LLMUnavailableError:
            stats.llm_available = False
            return
        except Exception as exc:
            stats.rejected.append(f"extraction post {post_id}: {type(exc).__name__}")
            continue
        db.add(
            m.ExtractionRun(
                kind="a3_extraction",
                model="a3_forum_extraction",  # routing task; model ids live in llm_routing.yaml
                prompt_version=a3.load_prompt("a3_extraction").version,
                output={"post_id": post_id, "text_version": _version(text), **found.model_dump()},
                status="ok",
            )
        )
        stats.extracted += 1


def _ratings(
    db: Session, today: dt.date
) -> tuple[dict[int, dict[str, list[Rating]]], dict[int, str]]:
    """Page id -> key -> ratings, and page id -> course code."""
    per_page: dict[int, dict[str, list[Rating]]] = defaultdict(lambda: defaultdict(list))
    code_of: dict[int, str] = dict(
        db.execute(
            sa.select(m.CourseInstructor.id, m.Course.code).join(
                m.Course, m.Course.id == m.CourseInstructor.course_id
            )
        )
        .tuples()
        .all()
    )
    reviews = db.execute(
        sa.select(m.Post.id, m.Post.course_instructor_id, m.Post.created_day, m.ReviewRating)
        .join(m.ReviewRating, m.ReviewRating.post_id == m.Post.id)
        .where(m.Post.status == "visible", m.Post.kind == "review")
    ).all()
    for post_id, page_id, day, rating in reviews:
        w = rating_weight("review", day, today)
        per_page[page_id]["workload_hours"].append(Rating(rating.workload_hours, w, post_id))
        per_page[page_id]["difficulty"].append(Rating(rating.difficulty, w, post_id))
        per_page[page_id]["intellectual_intensity"].append(
            Rating(rating.intellectual_intensity, w, post_id)
        )
        per_page[page_id]["recommend_rate"].append(
            Rating(1.0 if rating.would_recommend else 0.0, w, post_id)
        )
        for key in ("pace", "grading_strictness"):  # optional questions (Q11)
            answer = getattr(rating, key)
            if answer is not None:
                per_page[page_id][key].append(Rating(float(answer), w, post_id))
    # Text values: discussion posts only (a review's own ratings already count), from the
    # extraction of the post's current text, and one value per author, page and key (the
    # median of everything that author's posts on the page say), so neither one post nor one
    # person posting several times can count as several ratings.
    extracted = _extracted(db)
    discussions = db.execute(
        sa.select(
            m.Post.id,
            m.Post.course_instructor_id,
            m.Post.author_ref,
            m.Post.created_day,
            m.Post.title,
            m.Post.body_md,
        )
        .outerjoin(m.ReviewRating, m.ReviewRating.post_id == m.Post.id)
        .where(m.Post.status == "visible", m.ReviewRating.post_id.is_(None))
        .order_by(m.Post.id)
    ).all()
    groups: dict[tuple[int, str], dict[str, Any]] = {}
    for pid, page, ref, day, title, body in discussions:
        out = extracted.get(pid)
        if out is None or out.get("text_version") != _version(_text(title, body)):
            continue
        group = groups.setdefault(
            (page, ref or f"post:{pid}"),
            {"post_id": pid, "day": day, "workload_hours": [], "difficulty": []},
        )
        group["day"] = max(group["day"], day)
        group["workload_hours"] += [float(x["hours"]) for x in out.get("workload_mentions", [])]
        group["difficulty"] += [a3.DIFFICULTY[x["level"]] for x in out.get("difficulty_cues", [])]
    for (page, _), group in groups.items():
        w = rating_weight("text", group["day"], today)
        for key in ("workload_hours", "difficulty"):
            if group[key]:
                value = statistics.median(group[key])
                per_page[page][key].append(Rating(value, w, group["post_id"], "text"))
    return per_page, code_of


def _publish(
    db: Session,
    subject_type: str,
    subject_id: str,
    key: str,
    ratings: list[Rating],
    prior: Prior | None,
    estimate: float | None,
) -> bool:
    """Write the subject's value: forum-derived when n (distinct posts) >= MIN_N, else its
    estimate."""
    if count_posts(ratings) >= MIN_N:
        est = posterior(key, ratings, prior)
        if est is None:
            return False
        evidence: dict[str, Any] = {
            "post_ids": sorted({r.post_id for r in ratings if r.post_id is not None}),
            "structured": sum(r.source == "review" for r in ratings),
            "from_text": sum(r.source == "text" for r in ratings),
        }
        if prior is not None:
            evidence["prior"] = {
                "kind": prior.kind,
                "mean": round(prior.mean, 3),
                "weight": prior.weight,
            }
        if estimate is not None:
            evidence["estimate"] = estimate
        values: dict[str, Any] = {
            "value": est.value,
            "ci_low": est.ci_low,
            "ci_high": est.ci_high,
            "n": est.n,
            "method": "blend" if prior is not None else "forum",
            "evidence": evidence,
        }
    elif estimate is not None:
        values = {
            "value": estimate,
            "ci_low": None,
            "ci_high": None,
            "n": 0,
            "method": "prior",
            "evidence": {"estimate": estimate},
        }
    else:
        db.execute(
            sa.delete(m.AttributeValue).where(
                m.AttributeValue.subject_type == subject_type,
                m.AttributeValue.subject_id == subject_id,
                m.AttributeValue.key == key,
            )
        )
        return False
    _upsert_attribute(db, subject_type, subject_id, key, values)
    return True


def _aggregate(db: Session, today: dt.date, stats: Stats) -> None:
    per_page, code_of = _ratings(db, today)
    estimates = _estimates(db)
    per_course: dict[str, dict[str, list[Rating]]] = defaultdict(lambda: defaultdict(list))
    per_department: dict[str, dict[str, list[Rating]]] = defaultdict(lambda: defaultdict(list))
    # A cross-listed course has one page per instructor under all its codes (P08-5), so its
    # ratings count for every code it is listed under.
    siblings = {code: crosslisted_codes(db, code) for code in set(code_of.values())}
    for page, by_key in per_page.items():
        code = code_of.get(page)
        if code is None:
            continue
        for key, ratings in by_key.items():
            for sibling in siblings[code]:
                per_course[sibling][key] += ratings
            for dept_code in {c.split(" ")[0] for c in siblings[code]}:
                per_department[dept_code][key] += ratings
    courses = sorted({c for codes in siblings.values() for c in codes})
    for code in courses:
        for key in FORUM_KEYS:
            ratings = per_course[code][key]
            # The department's average without this course's own posts.
            own = {r.post_id for r in ratings}
            dept = [r for r in per_department[code.split(" ")[0]][key] if r.post_id not in own]
            estimate = estimates.get(code, {}).get(key)
            prior = department_prior(dept) or (
                Prior(estimate, K_ESTIMATE, "estimate") if estimate is not None else None
            )
            stats.attributes += _publish(db, "course", code, key, ratings, prior, estimate)
    for page, code in code_of.items():
        for key in FORUM_KEYS:
            ratings = per_page[page][key]
            # The department's average without this page's own posts (SPEC: m is the
            # department-level average, else the estimate).
            own = {x.post_id for x in ratings}
            dept = [r for r in per_department[code.split(" ")[0]][key] if r.post_id not in own]
            estimate = estimates.get(code, {}).get(key)
            prior = department_prior(dept) or (
                Prior(estimate, K_ESTIMATE, "estimate") if estimate is not None else None
            )
            stats.attributes += _publish(
                db, "course_instructor", str(page), key, ratings, prior, estimate
            )


def _summaries(db: Session, llm: LLM, today: dt.date, stats: Stats) -> None:
    pages = db.execute(
        sa.select(m.Post.course_instructor_id, sa.func.count())
        .where(m.Post.status == "visible")
        .group_by(m.Post.course_instructor_id)
    ).all()
    for page_id, n_posts in pages:
        if not stats.llm_available:
            return
        row = db.get(m.ForumSummary, page_id)
        fresh = row is not None and (today - row.computed_at).days < REBUILD_AFTER_DAYS
        if row is not None and fresh and n_posts < row.n_posts + REBUILD_AFTER_POSTS:
            continue
        posts = db.execute(
            sa.select(m.Post.id, m.Post.title, m.Post.body_md)
            .where(m.Post.course_instructor_id == page_id, m.Post.status == "visible")
            .order_by(m.Post.score.desc(), m.Post.id)
            .limit(40)
        ).all()
        try:
            summary = a3.summarize(
                llm, [(pid, f"{title or ''}\n{body}") for pid, title, body in posts]
            )
        except LLMUnavailableError:
            stats.llm_available = False
            return
        except a3.SummaryRejectedError as exc:
            stats.rejected.append(f"summary page {page_id}: {exc}")
            continue
        except Exception as exc:
            stats.rejected.append(f"summary page {page_id}: {type(exc).__name__}")
            continue
        values = {
            "text": summary.text,
            "citations": [{"post_id": c} for c in summary.citations],
            "model": "a3_forum_summary",  # routing task; the model id lives in llm_routing.yaml
            "n_posts": n_posts,
            "computed_at": today,
        }
        stmt = insert(m.ForumSummary).values(course_instructor_id=page_id, **values)
        db.execute(stmt.on_conflict_do_update(index_elements=["course_instructor_id"], set_=values))
        stats.summaries += 1


def _prune_summaries(db: Session) -> None:
    """Delete summaries that cite a post no longer visible (also on pages with no visible post
    left); pages that still have posts get a new one in `_summaries`."""
    for row in db.scalars(sa.select(m.ForumSummary)).all():
        if hidden_citations(db, row):
            db.delete(row)
    db.flush()


def run_nightly(db: Session, llm: LLM, today: dt.date | None = None) -> Stats:
    today = today or dt.date.today()
    stats = Stats()
    _definitions(db)
    _cold_start(db, llm, stats)
    db.flush()
    _extract(db, llm, stats)
    db.flush()
    _aggregate(db, today, stats)
    _prune_summaries(db)
    _summaries(db, llm, today, stats)
    db.commit()
    for problem in stats.rejected:
        log.warning("a3 rejected: %s", problem)
    return stats
