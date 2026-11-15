"""Forum security and privacy (prompt 08): sanitized markdown, the email/phone scrub, and a
leaked-database simulation showing posts on different pages cannot be joined to one account
without the server key. Also the development-only demo seed."""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from collections.abc import Iterator
from html.parser import HTMLParser
from typing import Any

import pytest
from api.auth.hashing import author_ref
from api.config import get_settings
from api.db import models as m
from api.forum.demo import DemoRefusedError, remove_demo, seed_demo
from api.forum.markdown import render_markdown
from api.forum.scrub import EMAIL_MARK, PHONE_MARK, scrub
from auth_test_support import migrated_database
from forum_test_support import REVIEW, ForumEnv, discussion, forum_env
from sqlalchemy import select, text

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg/onload=alert(1)>",
    '<a href="javascript:alert(1)">x</a>',
    "[click](javascript:alert(1))",
    "[click](JaVaScRiPt:alert(1))",
    "[click](&#106;avascript:alert(1))",
    "[click](  javascript:alert(1))",
    "[click](vbscript:msgbox(1))",
    "[click](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)",
    "<javascript:alert(1)>",
    "![x](https://tracker.example/pixel.png)",
    '![x](x" onerror="alert(1))',
    '[x](https://ok.example/" onmouseover="alert(1))',
    "<iframe src=https://evil.example></iframe>",
    "<style>body{display:none}</style>",
    '<div style="background:url(javascript:alert(1))">x</div>',
    "```\n</code></pre><script>alert(1)</script>\n```",
    "`<script>alert(1)</script>`",
    "[x](//evil.example/path)",
    "[x](/admin/moderation)",
]

ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "del",
    "s",
    "code",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "li",
    "a",
    "hr",
}


class _Elements(HTMLParser):
    """The real elements and attributes a browser would build (escaped text is just text)."""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, list[tuple[str, str | None]]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, attrs))


def _assert_safe(html: str) -> None:
    parser = _Elements()
    parser.feed(html)
    for tag, attrs in parser.elements:
        assert tag in ALLOWED_TAGS, f"unexpected <{tag}> in {html!r}"
        for name, value in attrs:
            assert name in {"href", "rel", "start"}, f"unexpected attribute {name} in {html!r}"
            if name == "href":
                assert (value or "").startswith(("https://", "http://")), html


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_payloads_are_neutralized(payload: str) -> None:
    _assert_safe(render_markdown(payload))


def test_markdown_keeps_safe_formatting() -> None:
    html = render_markdown(
        "**Bold**, _it_, ~~old~~, `code`, [docs](https://example.edu/a?b=1)\n\n- a\n- b"
    )
    assert "<strong>Bold</strong>" in html and "<em>it</em>" in html and "<s>old</s>" in html
    assert (
        '<a href="https://example.edu/a?b=1" rel="nofollow noopener noreferrer ugc">docs</a>'
        in html
    )
    assert "<ul>" in html
    assert "<h1>" not in render_markdown("# Not a heading")


def test_scrub_removes_emails_and_phone_numbers() -> None:
    text_in = (
        "Write to jdoe@uchicago.edu, J.Doe+tag@cs.uchicago.edu or jdoe at uchicago dot edu "
        "or jdoe [at] gmail [dot] com. Call 773-702-1234, (773) 702 1234, +1 773.702.1234, "
        "7737021234 or +44 20 7946 0958."
    )
    out = scrub(text_in)
    assert out.count(EMAIL_MARK) == 4
    assert out.count(PHONE_MARK) == 5
    assert "@" not in out and not re.search(r"\d{3}.?\d{4}", out)
    harmless = "CMSC 14100 took 10-12 hours a week in 2026; problem set 3 was due at 5 pm."
    assert scrub(harmless) == harmless


# --------------------------------------------------------------------- leaked database


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def f(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[ForumEnv]:
    with forum_env(db_url, monkeypatch) as fenv:
        yield fenv


FORUM_TABLES = [
    "post",
    "review_rating",
    "comment",
    "vote",
    "pseudonym",
    "report",
    "moderation_action",
]


def _dump(f: ForumEnv) -> dict[str, list[dict[str, Any]]]:
    """What an attacker with a copy of the database (and no server key) sees."""
    with f.env.engine.connect() as conn:
        return {
            t: [dict(r._mapping) for r in conn.execute(text(f"SELECT * FROM {t}"))]
            for t in FORUM_TABLES
        }


@pytest.mark.db
def test_xss_payloads_through_the_api(f: ForumEnv) -> None:
    user = f.user()
    for payload in XSS_PAYLOADS[:6]:
        created = user.post(
            f"/forum/pages/{f.pages['a_doe']}/posts", discussion("t", payload)
        ).json()
        _assert_safe(created["body_html"])
        c = user.post(f"/forum/posts/{created['id']}/comments", {"body_md": payload}).json()
        _assert_safe(c["body_html"])


@pytest.mark.db
def test_leaked_database_cannot_join_posts_across_pages(f: ForumEnv) -> None:
    alice, bob = f.user("alice-anon"), f.user("bob-anon")
    # Alice is active on two pages: posts, a review, a comment, votes and a report on each.
    for page, term in (("a_doe", "2099-AU"), ("b_doe", "2100-WI")):
        p = alice.post(f"/forum/pages/{f.pages[page]}/posts", discussion(f"q {page}")).json()
        alice.post(f"/forum/pages/{f.pages[page]}/posts", {**REVIEW, "term_taken": term})
        alice.post(f"/forum/posts/{p['id']}/comments", {"body_md": "me again"})
        alice.post("/forum/votes", {"target_type": "post", "target_id": p["id"], "value": 1})
        theirs = bob.post(f"/forum/pages/{f.pages[page]}/posts", discussion("bob")).json()
        alice.post(
            "/forum/reports", {"target_type": "post", "target_id": theirs["id"], "reason": "spam"}
        )

    dump = _dump(f)
    alice_id = uuid.UUID(alice.account_id)
    blob = repr(dump).lower()
    # 1. No account id, username or email appears anywhere in the forum tables.
    for needle in (str(alice_id), alice_id.hex, "alice-anon", "uchicago.edu"):
        assert needle not in blob, needle

    # 2. Every identity column of Alice's rows differs between the two pages: nothing to join on.
    page_a, page_b = f.pages["a_doe"], f.pages["b_doe"]
    posts = {r["id"]: r for r in dump["post"]}

    def page_of(table: str, row: dict[str, Any]) -> int:
        if table in ("post", "pseudonym"):
            return int(row["course_instructor_id"])
        if table == "comment":
            return int(posts[row["post_id"]]["course_instructor_id"])
        if table in ("vote", "report"):
            target = posts.get(row["target_id"]) if row["target_type"] == "post" else None
            assert target is not None
            return int(target["course_instructor_id"])
        raise AssertionError(table)

    identity_cols = {
        "post": ["author_ref", "pseudonym_id"],
        "comment": ["author_ref", "pseudonym_id"],
        "pseudonym": ["author_ref", "handle"],
        "vote": ["voter_ref"],
        "report": ["reporter_ref"],
    }
    values: dict[int, set[Any]] = {page_a: set(), page_b: set()}
    for table, cols in identity_cols.items():
        for row in dump[table]:
            for col in cols:
                if row[col] is not None:
                    values[page_of(table, row)].add(
                        (col.replace("voter_", "author_").replace("reporter_", "author_"), row[col])
                    )
    assert values[page_a] and values[page_b]
    assert not ({v for _, v in values[page_a]} & {v for _, v in values[page_b]})

    # 3. Refs cannot be recomputed without the key: a guessed key matches nothing.
    stored_refs = {r["author_ref"] for r in dump["post"]}
    for guess in (b"", b"dev-only", b"quarterly", alice_id.bytes):
        wrong = hmac.new(
            guess, alice_id.bytes + b"|" + str(page_a).encode(), hashlib.sha256
        ).hexdigest()
        assert wrong not in stored_refs
    assert (
        hashlib.sha256(alice_id.bytes + b"|" + str(page_a).encode()).hexdigest() not in stored_refs
    )

    # 4. With the key (the server), the posts are found again: account deletion relies on this.
    with_key = {author_ref(alice_id, page_a), author_ref(alice_id, page_b)}
    alice_posts = [r for r in dump["post"] if r["author_ref"] in with_key]
    assert len(alice_posts) == 4
    # 5. Dates are day-level: no timestamp column in the forum tables.
    for rows in dump.values():
        for row in rows:
            assert not any(type(v).__name__ == "datetime" for v in row.values())


@pytest.mark.db
def test_account_deletion_finds_forum_rows_by_recomputing_refs(f: ForumEnv) -> None:
    user = f.user("leaving-soon")
    p = user.post(f"/forum/pages/{f.pages['a_doe']}/posts", discussion()).json()
    user.post(f"/forum/pages/{f.pages['b_doe']}/posts", discussion()).json()
    user.post("/forum/votes", {"target_type": "post", "target_id": p["id"], "value": 1})
    resp = user.post("/account/delete", {"password": "correct horse battery", "posts": "keep"})
    assert resp.status_code == 204, resp.text
    dump = _dump(f)
    assert all(r["author_ref"] is None for r in dump["post"])
    assert dump["vote"] == [] and dump["pseudonym"] == []


# ---------------------------------------------------------------------------- demo seed


@pytest.mark.db
def test_seed_forum_demo_is_development_only(f: ForumEnv, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    with f.env.db() as db:
        db.add_all(
            [
                m.Course(
                    catalog_year="2099-00",
                    subject="CMSC",
                    number="14100",
                    code="CMSC 14100",
                    title="Intro",
                ),
                m.Course(
                    catalog_year="2099-00",
                    subject="MATH",
                    number="15100",
                    code="MATH 15100",
                    title="Calc",
                ),
            ]
        )
        db.commit()
        monkeypatch.setattr(settings, "environment", "test")
        with pytest.raises(DemoRefusedError):
            seed_demo(db)
        monkeypatch.setattr(settings, "environment", "development")
        counts = seed_demo(db)
        assert (
            counts["instructors"] == 5 and counts["pages"] == 3 and counts["skipped_courses"] == 3
        )
        names = db.scalars(
            select(m.Instructor.display_name).where(m.Instructor.slug.startswith("demo-"))
        ).all()
        assert sorted(names) == [f"Demo Instructor {c}" for c in "ABCDE"]
        assert db.scalar(select(m.Post.id).limit(1)) is not None
        again = seed_demo(db)  # idempotent
        assert again["instructors"] == 0 and again["posts"] == 0
        assert remove_demo(db) == 5
        assert (
            db.scalars(select(m.Instructor).where(m.Instructor.slug.startswith("demo-"))).all()
            == []
        )
        assert db.scalars(select(m.Post)).all() == []
