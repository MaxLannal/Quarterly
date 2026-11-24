"""`uv run python -m api.commons.demo`: demo QUESTIONS in the Commons, for local development.

About fourteen realistic questions on real 2026-27 courses, a few replies phrased as questions
or suggestions (none claims to have taken a course, none is a review), tags and a few votes.
Every author is made up (a random ref that matches no account), so the rows belong to nobody and
account deletion never touches them. The bot's answers are not seeded: open a question and the
bot answers it (with the live AI when it is on). Idempotent: does nothing when the demo is
already there. Refuses to run unless ENVIRONMENT=development. `--remove` deletes it again.
"""

from __future__ import annotations

import datetime as dt
import random
import secrets
import sys
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.agents.live import CAMPUS_YEAR
from api.commons.service import handle_for
from api.config import get_settings
from api.db import models as m
from api.db.session import get_engine


class DemoRefusedError(RuntimeError):
    pass


@dataclass
class Reply:
    body: str
    children: list[Reply] = field(default_factory=list)


@dataclass
class Question:
    title: str
    body: str
    course: str | None
    tags: list[str]
    days_ago: int
    votes: int
    replies: list[Reply] = field(default_factory=list)


#: The marker the idempotency check looks for (the first question's title).
QUESTIONS: list[Question] = [
    Question(
        "Is CMSC 14100 OK with no programming background?",
        "I've never written a line of code, but I'm curious about computer science. Would "
        "CMSC 14100 be a reasonable first course, or should I start with something gentler "
        "and take it later?",
        "CMSC 14100",
        ["first-year", "cs"],
        2,
        9,
        [
            Reply(
                "Has anyone checked whether the course page lists a prerequisite? That might "
                "settle it.",
                [Reply("Good idea. I'd also ask about the placement test before registration.")],
            ),
            Reply("Following, since I'm wondering the same thing about CMSC 14200 afterwards."),
        ],
    ),
    Question(
        "MATH 15300 vs MATH 16300 for a likely math major?",
        "I placed into the third quarter of calculus. If I'm fairly sure I'll major in math, "
        "is the honors version (MATH 16300) worth it, or does MATH 15300 keep more options "
        "open?",
        "MATH 16300",
        ["math", "first-year"],
        5,
        12,
        [Reply("Would a math department adviser be the right person to ask before you decide?")],
    ),
    Question(
        "Which Hum sequence has the most discussion and the least lecture?",
        "I learn best in seminar-style classes. Among the Humanities Core sequences (HUMA "
        "11000, HUMA 13500, HUMA 17000 and the rest), which ones are mostly discussion?",
        None,
        ["core", "humanities"],
        8,
        15,
        [
            Reply("Does anyone know if section sizes differ between the sequences?"),
            Reply("Maybe the course descriptions say how class time is split?"),
        ],
    ),
    Question(
        "How do people fit study abroad with an Econ major?",
        "I'd love a quarter abroad in my second or third year. How do Econ majors usually fit "
        "it around ECON 20000 and ECON 20100?",
        "ECON 20000",
        ["study-abroad", "econ"],
        11,
        7,
        [Reply("Could you check which quarters the sequence is usually offered and plan back?")],
    ),
    Question(
        "Any advice for getting into a quantum computing lab as a first-year?",
        "I'm really interested in quantum computing. Which courses would make me a credible "
        "undergraduate researcher, and how early is too early to email a lab?",
        None,
        ["research", "quantum", "first-year"],
        3,
        11,
        [Reply("Would PHYS 13100 or PHYS 14100 be the usual starting point for this?")],
    ),
    Question(
        "PHYS 14100 or PHYS 13100 if I'm into CS?",
        "I'm leaning toward computer science but want real physics too. Is the honors "
        "mechanics course worth the extra work, or is PHYS 13100 enough?",
        "PHYS 14100",
        ["physics", "cs"],
        6,
        5,
    ),
    Question(
        "STAT 22000 or STAT 23400 for a Public Policy major?",
        "Both seem to show up in planning advice. Which one fits better if I want to do "
        "quantitative policy work later, alongside PBPL 22200?",
        "STAT 23400",
        ["statistics", "public-policy"],
        9,
        4,
    ),
    Question(
        "CHEM 10100 or CHEM 11100 for pre-med with weak high-school chemistry?",
        "My high-school chemistry was thin. Should I start with CHEM 10100, or is CHEM 11100 "
        "doable if I'm willing to work hard?",
        "CHEM 11100",
        ["pre-med", "chemistry"],
        13,
        6,
        [Reply("Is there a placement exam for chemistry too, like for math?")],
    ),
    Question(
        "Is CMSC 27200 manageable alongside MATH 20700?",
        "Thinking about pairing Theory of Algorithms with Honors Analysis next year. Is that "
        "a reasonable quarter, or too much proof-writing at once?",
        "CMSC 27200",
        ["workload", "cs", "math"],
        4,
        8,
    ),
    Question(
        "What is SOSC 15100 like for someone new to political theory?",
        "I haven't read much political philosophy. Is Classics of Social and Political "
        "Thought a good fit for a beginner, or is another Social Sciences sequence gentler?",
        "SOSC 15100",
        ["core", "social-sciences"],
        16,
        3,
    ),
    Question(
        "FREN 10100 or SPAN 10100 for an absolute beginner?",
        "I need to meet the language requirement and have never studied either. Which "
        "elementary sequence tends to be friendlier for a total beginner?",
        "SPAN 10100",
        ["language", "first-year"],
        7,
        2,
        [Reply("Do both sequences meet every day? That might matter for your schedule.")],
    ),
    Question(
        "Does MUSI 10100 work for the arts Core if I can't read music?",
        "Introduction to Western Art Music sounds great, but I can't read sheet music at all. "
        "Is that a problem, and does it count toward the arts part of the Core?",
        "MUSI 10100",
        ["core", "arts"],
        10,
        5,
    ),
    Question(
        "Good first data science course: CMSC 21800 or STAT 22000?",
        "I want to learn data science properly. Which is the better first step, and what "
        "should I take before it?",
        "CMSC 21800",
        ["data-science", "cs", "statistics"],
        1,
        3,
    ),
    Question(
        "LING 20001 as a first-year with no linguistics background?",
        "Introduction to Linguistics looks fascinating. Can a first-year with no background "
        "take it, and does it lead anywhere if I end up liking it?",
        "LING 20001",
        ["linguistics", "first-year"],
        18,
        4,
    ),
]


def _check_environment() -> None:
    if get_settings().environment != "development":
        raise DemoRefusedError("demo data only in development (ENVIRONMENT=development)")


def _ref() -> str:
    return secrets.token_hex(32)  # shaped like a commons_ref, matching no account


def _upvote(target_type: str, target_id: int) -> m.CommonsVote:
    return m.CommonsVote(target_type=target_type, target_id=target_id, voter_ref=_ref(), value=1)


def _add_replies(
    db: Session,
    thread: m.CommonsThread,
    replies: list[Reply],
    *,
    parent: m.CommonsReply | None,
    day: dt.date,
    rng: random.Random,
) -> None:
    for item in replies:
        ref = _ref()
        handle_for(db, thread.id, ref)
        reply = m.CommonsReply(
            thread_id=thread.id,
            parent_id=parent.id if parent else None,
            depth=parent.depth + 1 if parent else 0,
            author_ref=ref,
            kind="human",
            body_md=item.body,
            status="visible",
            created_day=day,
        )
        db.add(reply)
        db.flush()
        for _ in range(rng.randint(0, 3)):
            db.add(_upvote("reply", reply.id))
        db.flush()
        reply.score = int(
            db.scalar(
                sa.select(sa.func.count()).where(
                    m.CommonsVote.target_type == "reply", m.CommonsVote.target_id == reply.id
                )
            )
            or 0
        )
        thread.last_reply_id = reply.id
        _add_replies(db, thread, item.children, parent=reply, day=day, rng=rng)


def seed(db: Session) -> int:
    """Add the demo questions; returns how many were added (0 when already there)."""
    _check_environment()
    if db.scalar(sa.select(m.CommonsThread.id).where(m.CommonsThread.title == QUESTIONS[0].title)):
        return 0
    rng = random.Random(2026)
    today = dt.date.today()
    added = 0
    for q in QUESTIONS:
        course_id = None
        if q.course:
            course_id = db.scalar(
                sa.select(m.Course.id).where(
                    m.Course.catalog_year == CAMPUS_YEAR, m.Course.code == q.course
                )
            )
            if course_id is None:
                continue  # not in this catalog: skip rather than invent
        day = today - dt.timedelta(days=q.days_ago)
        ref = _ref()
        thread = m.CommonsThread(
            course_id=course_id,
            title=q.title,
            body_md=q.body,
            tags=q.tags,
            bot_state="pending",
            status="visible",
            created_day=day,
        )
        db.add(thread)
        db.flush()
        thread.author_ref = ref
        handle_for(db, thread.id, ref)
        for _ in range(q.votes):
            db.add(_upvote("thread", thread.id))
        thread.score = q.votes
        reply_day = min(today, day + dt.timedelta(days=1))
        _add_replies(db, thread, q.replies, parent=None, day=reply_day, rng=rng)
        db.flush()
        thread.reply_count = int(
            db.scalar(
                sa.select(sa.func.count()).where(
                    m.CommonsReply.thread_id == thread.id, m.CommonsReply.kind == "human"
                )
            )
            or 0
        )
        added += 1
    db.commit()
    return added


def remove(db: Session) -> int:
    """Delete the demo questions (by title) with everything under them."""
    _check_environment()
    titles = [q.title for q in QUESTIONS]
    ids = list(db.scalars(sa.select(m.CommonsThread.id).where(m.CommonsThread.title.in_(titles))))
    if ids:
        replies = list(
            db.scalars(sa.select(m.CommonsReply.id).where(m.CommonsReply.thread_id.in_(ids)))
        )
        for target_type, targets in (("thread", ids), ("reply", replies)):
            if targets:
                db.execute(
                    sa.delete(m.CommonsVote).where(
                        m.CommonsVote.target_type == target_type,
                        m.CommonsVote.target_id.in_(targets),
                    )
                )
        db.execute(sa.delete(m.CommonsThread).where(m.CommonsThread.id.in_(ids)))
    db.commit()
    return len(ids)


def main(argv: list[str]) -> int:
    try:
        with Session(get_engine()) as db:
            if "--remove" in argv:
                print(f"commons demo: removed {remove(db)} questions")
            else:
                n = seed(db)
                print(f"commons demo: added {n} questions" if n else "commons demo: already seeded")
    except DemoRefusedError as exc:
        print(f"commons demo: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
