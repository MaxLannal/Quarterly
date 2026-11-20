"""The Commons (docs/BEST-OF-UCHICAGO-PLAN.md): identity, threads, listing and filters, public
reading, replies and their tree, edits and deletions, votes, acceptance, follows, presence,
reports, rate limits, the email scrub and the account export/deletion helpers."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from api.auth.hashing import author_ref
from api.auth.ratelimit import HOUR, Limit
from api.commons import service
from api.commons.account import export_commons, forget_commons
from api.commons.identity import commons_ref
from api.db import models as m
from api.routers import commons as commons_router
from api.schemas.commons import normalize_tags
from auth_test_support import migrated_database
from test_commons_support import CommonsEnv, commons_env, walk

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def c(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[CommonsEnv]:
    with commons_env(db_url, monkeypatch) as cenv:
        yield cenv


def ids(listing: dict[str, Any]) -> list[int]:
    return [t["id"] for t in listing["items"]]


# ------------------------------------------------------------------------------ identity


@pytest.mark.parametrize("thread_id", [1, 7, 12345])
def test_commons_ref_is_stable_and_domain_separated_from_the_forum(thread_id: int) -> None:
    account = uuid.uuid4()
    ref = commons_ref(account, thread_id)
    assert ref == commons_ref(account, thread_id) and len(ref) == 64
    assert ref != author_ref(account, thread_id)  # same ids, other domain
    assert ref != commons_ref(account, thread_id + 1)
    assert ref != commons_ref(uuid.uuid4(), thread_id)


def test_text_helpers() -> None:
    assert service.excerpt("**Bold** and [a link](https://x.org)\n\n- item `code`") == (
        "Bold and a link item code"
    )
    long = " ".join(["word"] * 100)
    cut = service.excerpt(long)
    assert len(cut) <= 200 and cut.endswith("…")
    html = (
        '<p>Take CMSC 14100 then <code>CMSC 14200</code> or <a href="https://x">MATH 15300</a></p>'
    )
    linked = service.link_courses(html, {"CMSC 14100", "CMSC 14200", "MATH 15300"})
    assert '<a href="/courses/CMSC%2014100" data-course="CMSC 14100">CMSC 14100</a>' in linked
    assert "<code>CMSC 14200</code>" in linked  # not inside code
    assert linked.count("/courses/") == 1  # not inside an existing link
    assert normalize_tags(["Study Abroad", "study_abroad", "econ"]) == ["study-abroad", "econ"]
    with pytest.raises(ValueError):
        normalize_tags(["a", "b", "c", "d", "e", "f"])
    with pytest.raises(ValueError):
        normalize_tags(["x" * 25])
    assert service.summons_bot("Hey @quarterly, which one?") and service.summons_bot("@AI?")
    assert not service.summons_bot("mail me at me@ai.com") and not service.summons_bot("ai")


# ------------------------------------------------------------------------- create and read


def test_asking_creates_a_thread_with_a_handle_and_a_pending_bot(c: CommonsEnv) -> None:
    asker = c.user("asker")
    out = asker.ask(
        "Is CMSC 14100 OK with no programming background?",
        body_md="I have never coded. Is **CMSC 14100** fine, or MATH 15300 first? "
        "Email me at jdoe@uchicago.edu or 773-702-1234.",
        course_code="cmsc14100",
        tags=["First Year", "cs"],
    )
    assert out["course"] == {"code": "CMSC 14100", "title": "Introduction to Computer Science I"}
    assert out["tags"] == ["first-year", "cs"]
    assert out["bot_state"] == "pending" and not out["has_bot_answer"]
    assert out["is_mine"] and out["handle"] not in ("", "Anonymous")
    assert "jdoe@uchicago.edu" not in out["body_md"] and "[email removed]" in out["body_md"]
    assert "773-702-1234" not in out["body_md"] and "[phone removed]" in out["body_md"]
    assert [x["code"] for x in out["mentions"]] == ["CMSC 14100", "MATH 15300"]
    assert 'href="/courses/MATH%2015300"' in out["body_html"]
    with c.env.db() as db:
        thread = db.get(m.CommonsThread, out["id"])
        assert thread is not None
        assert thread.author_ref == commons_ref(uuid.UUID(asker.account_id), thread.id)
        assert str(asker.account_id) not in str(thread.author_ref)
    # Another reader sees the handle but not the markdown source and not "mine".
    other = c.user("reader").thread(out["id"])
    assert other["handle"] == out["handle"] and not other["is_mine"] and other["body_md"] is None


def test_reading_is_public_but_writing_needs_a_login(c: CommonsEnv) -> None:
    asker = c.user()
    thread = asker.ask("Which Hum sequence has the most discussion?")
    anon = c.anon()
    assert anon.get("/commons/threads").json()["total"] == 1
    detail = anon.get(f"/commons/threads/{thread['id']}")
    assert detail.status_code == 200 and not detail.json()["is_mine"]
    assert anon.get(f"/commons/threads/{thread['id']}/presence").status_code == 200
    for url, body in (
        ("/commons/threads", {"title": "A logged-out question"}),
        (f"/commons/threads/{thread['id']}/replies", {"body_md": "hi"}),
        ("/commons/votes", {"target_type": "thread", "target_id": thread["id"], "value": 1}),
        (f"/commons/threads/{thread['id']}/accept", {"reply_id": None}),
        (f"/commons/threads/{thread['id']}/follow", {"follow": True}),
        (f"/commons/threads/{thread['id']}/typing", None),
        ("/commons/reports", {"target_type": "thread", "target_id": thread["id"], "reason": "x"}),
    ):
        assert anon.post(url, json=body).status_code == 401, url
    assert anon.get("/commons/threads?mine=true").status_code == 401
    assert anon.get("/commons/threads/999999").status_code == 404


def test_validation(c: CommonsEnv) -> None:
    u = c.user()
    assert u.post("/commons/threads", {"title": "short"}).status_code == 422
    assert u.post("/commons/threads", {"title": "x" * 161}).status_code == 422
    unknown = u.post(
        "/commons/threads", {"title": "What about FAKE 99999?", "course_code": "FAKE 99999"}
    )
    assert unknown.status_code == 422 and "no course" in unknown.json()["detail"]
    too_many = u.post("/commons/threads", {"title": "Many tags here", "tags": list("abcdef")})
    assert too_many.status_code == 422
    assert (
        u.post("/commons/threads", {"title": "Bad tag here", "tags": ["no/slash"]}).status_code
        == 422
    )
    assert (
        u.post("/commons/threads", {"title": "Long body here", "body_md": "x" * 8001}).status_code
        == 422
    )
    t = u.ask("A fine question title")
    assert u.post(f"/commons/threads/{t['id']}/replies", {"body_md": "   "}).status_code == 422
    assert u.get("/commons/threads?limit=31").status_code == 422
    assert u.get("/commons/threads?cursor=abc").status_code == 422


def test_list_sorts_filters_and_pages(c: CommonsEnv) -> None:
    a, b = c.user("alpha"), c.user("bravo")
    t1 = a.ask(
        "MATH 15300 vs 16300 for a likely math major?", course_code="MATH 16300", tags=["math"]
    )
    t2 = a.ask("Is CMSC 14100 OK with no background?", course_code="CMSC 14100", tags=["cs"])
    t3 = b.ask(
        "How do people fit study abroad with an Econ major?",
        body_md="Thinking of Paris.",
        tags=["study-abroad"],
    )
    b.reply(t1["id"], "Have you looked at the placement test?")
    a.post("/commons/votes", {"target_type": "thread", "target_id": t3["id"], "value": 1})
    a.post("/commons/votes", {"target_type": "thread", "target_id": t3["id"], "value": 1})

    def get(query: str, user: Any = a) -> dict[str, Any]:
        resp = user.get(f"/commons/threads?{query}")
        assert resp.status_code == 200, resp.text
        out: dict[str, Any] = resp.json()
        return out

    assert ids(get("sort=new")) == [t3["id"], t2["id"], t1["id"]]
    assert ids(get("sort=top"))[0] == t3["id"]
    assert ids(get("sort=active"))[0] == t1["id"]  # the only one with a reply
    assert set(ids(get("sort=hot"))) == {t1["id"], t2["id"], t3["id"]}
    assert ids(get("sort=unanswered")) == [t3["id"], t2["id"]]
    assert ids(get("course=cmsc%2014100")) == [t2["id"]]
    assert ids(get("course=NOPE")) == []
    assert ids(get("subject=math")) == [t1["id"]]
    assert ids(get("tag=study-abroad")) == [t3["id"]]
    assert ids(get("q=paris")) == [t3["id"]]  # body text
    assert ids(get("q=16300")) == [t1["id"]]  # title text
    assert ids(get("mine=true&sort=new")) == [t2["id"], t1["id"]]
    assert ids(get("mine=true", user=b)) == [t3["id"]]
    listing = get("sort=new")
    first = next(t for t in listing["items"] if t["id"] == t1["id"])
    assert first["reply_count"] == 1 and first["answer_count"] == 1 and first["answered"]
    third = next(t for t in listing["items"] if t["id"] == t3["id"])
    assert third["score"] == 1 and third["my_vote"] == 1 and not third["is_mine"]
    page1 = get("sort=new&limit=2")
    assert ids(page1) == [t3["id"], t2["id"]] and page1["total"] == 3 and page1["next_cursor"]
    page2 = get(f"sort=new&limit=2&cursor={page1['next_cursor']}")
    assert ids(page2) == [t1["id"]] and page2["next_cursor"] is None


# ------------------------------------------------------------------------------- replies


def test_replies_nest_and_flatten_at_depth_four(c: CommonsEnv) -> None:
    asker, other = c.user(), c.user()
    t = asker.ask("Any advice for getting into a quantum lab?")
    first = other.reply(t["id"], "Have you emailed the PME advisers?")
    assert first["reply"]["depth"] == 0 and first["reply_count"] == 1
    chain = [first["reply"]]
    for i in range(5):
        user = asker if i % 2 == 0 else other
        chain.append(user.reply(t["id"], f"Level {i + 1}", parent=chain[-1]["id"])["reply"])
    assert [r["depth"] for r in chain] == [0, 1, 2, 3, 4, 4]
    assert chain[5]["parent_id"] == chain[3]["id"]  # a sibling of its parent at depth 4
    assert chain[1]["is_op"] and not chain[0]["is_op"]
    detail = asker.thread(t["id"])
    assert detail["reply_count"] == 6 and detail["last_reply_id"] == chain[5]["id"]
    tree = detail["replies"]
    assert len(tree) == 1 and tree[0]["children"][0]["id"] == chain[1]["id"]
    assert {r["id"] for r in walk(tree)} == {r["id"] for r in chain}
    mine = [r for r in walk(tree) if r["is_mine"]]
    assert all(r["body_md"] for r in mine) and len(mine) == 3
    assert all(r["body_md"] is None for r in walk(tree) if not r["is_mine"])
    # Handles: one per author on the thread, the asker's equal to the thread's.
    handles = {r["handle"] for r in walk(tree)}
    assert len(handles) == 2 and detail["handle"] in handles
    assert (
        other.post(
            f"/commons/threads/{t['id']}/replies", {"body_md": "x", "parent_id": 999999}
        ).status_code
        == 404
    )


def test_summon_flag(c: CommonsEnv) -> None:
    u = c.user()
    t = u.ask("PHYS 14100 or PHYS 13100 if I'm into CS?")
    assert u.reply(t["id"], "@quarterly what do you think?")["summon_bot"] is True
    assert u.reply(t["id"], "No bot please")["summon_bot"] is False


def test_only_authors_edit_and_delete(c: CommonsEnv) -> None:
    asker, other = c.user(), c.user()
    t = asker.ask("Is the CMSC 14100 placement test hard?", body_md="Asking ahead.")
    r = other.reply(t["id"], "Good question.")["reply"]
    url = f"/commons/threads/{t['id']}"
    assert other.patch(url, {"title": "Hijacked title here"}).status_code == 403
    assert other.delete(url).status_code == 403
    assert asker.patch(f"/commons/replies/{r['id']}", {"body_md": "mine now"}).status_code == 403
    assert asker.delete(f"/commons/replies/{r['id']}").status_code == 403
    edited = asker.patch(
        url,
        {
            "title": "Is the CMSC 14100 placement exam hard?",
            "tags": ["cs"],
            "course_code": "CMSC 14100",
        },
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["edited_day"] and body["tags"] == ["cs"] and body["course"]["code"] == "CMSC 14100"
    assert asker.patch(url, {"course_code": None}).json()["course"] is None
    assert asker.patch(url, {"course_code": "NOPE 12345"}).status_code == 422
    ok = other.patch(f"/commons/replies/{r['id']}", {"body_md": "Good question, really."})
    assert ok.status_code == 200 and ok.json()["edited_day"] and ok.json()["body_md"]
    # Deleting the question hides it from everyone but its author (a tombstone).
    assert asker.delete(url).status_code == 204
    assert other.get(url).status_code == 404 and c.anon().get(url).status_code == 404
    tomb = asker.get(url).json()
    assert tomb["status"] == "deleted" and tomb["replies"] == [] and tomb["title"] == "[deleted]"
    assert asker.get("/commons/threads").json()["total"] == 0
    assert other.post(f"{url}/replies", {"body_md": "late"}).status_code == 404
    with c.env.db() as db:
        thread = db.get(m.CommonsThread, t["id"])
        assert thread is not None and thread.body_md == "" and thread.status == "deleted"


def test_deleted_replies_leave_a_tombstone_that_keeps_their_children(c: CommonsEnv) -> None:
    asker, other = c.user(), c.user()
    t = asker.ask("Which Hum sequence is the most discussion-heavy?")
    parent = other.reply(t["id"], "Parent answer")["reply"]
    child = asker.reply(t["id"], "A child reply", parent=parent["id"])["reply"]
    leaf = other.reply(t["id"], "A lonely leaf")["reply"]
    assert other.delete(f"/commons/replies/{parent['id']}").status_code == 204
    assert other.delete(f"/commons/replies/{leaf['id']}").status_code == 204
    detail = asker.thread(t["id"])
    assert len(detail["replies"]) == 1  # the leaf is gone, the parent is a tombstone
    tomb = detail["replies"][0]
    assert tomb["status"] == "deleted" and tomb["body_html"] == "<p>[deleted]</p>"
    assert tomb["handle"] == "[deleted]" and tomb["body_md"] is None
    assert tomb["children"][0]["id"] == child["id"]
    assert detail["reply_count"] == 1 and detail["answer_count"] == 0
    assert other.patch(f"/commons/replies/{parent['id']}", {"body_md": "back"}).status_code == 409
    assert (
        asker.post(
            f"/commons/threads/{t['id']}/replies", {"body_md": "x", "parent_id": parent["id"]}
        ).status_code
        == 409
    )


# --------------------------------------------------------------------------------- votes


def test_votes(c: CommonsEnv) -> None:
    asker, voter = c.user(), c.user()
    t = asker.ask("MATH 15300 vs 16300 for a math major?")
    r = voter.reply(t["id"], "Depends on your proofs background.")["reply"]

    def vote(user: Any, kind: str, target: int, value: int) -> Any:
        return user.post(
            "/commons/votes", {"target_type": kind, "target_id": target, "value": value}
        )

    assert vote(asker, "thread", t["id"], 1).status_code == 403  # own question
    assert vote(voter, "reply", r["id"], 1).status_code == 403  # own reply
    assert vote(voter, "thread", t["id"], 1).json() == {"score": 1, "my_vote": 1}
    assert vote(voter, "thread", t["id"], 1).json() == {"score": 1, "my_vote": 1}  # idempotent
    assert vote(voter, "thread", t["id"], -1).json() == {"score": -1, "my_vote": -1}
    assert vote(voter, "thread", t["id"], 0).json() == {"score": 0, "my_vote": 0}
    assert vote(asker, "reply", r["id"], 1).json() == {"score": 1, "my_vote": 1}
    assert vote(asker, "reply", 999999, 1).status_code == 404
    detail = asker.thread(t["id"])
    assert detail["replies"][0]["score"] == 1 and detail["replies"][0]["my_vote"] == 1
    assert voter.thread(t["id"])["replies"][0]["my_vote"] == 0
    with c.env.db() as db:
        refs = set(db.scalars(sa.select(m.CommonsVote.voter_ref)))
        assert refs == {commons_ref(uuid.UUID(asker.account_id), t["id"])}


def test_accept_is_for_the_asker(c: CommonsEnv) -> None:
    asker, other = c.user(), c.user()
    t = asker.ask("How do people fit study abroad with an Econ major?")
    r = other.reply(t["id"], "Look at the Paris civ program.")["reply"]
    url = f"/commons/threads/{t['id']}/accept"
    assert other.post(url, {"reply_id": r["id"]}).status_code == 403
    assert asker.post(url, {"reply_id": 999999}).status_code == 404
    assert asker.post(url, {"reply_id": r["id"]}).json() == {"accepted_reply_id": r["id"]}
    detail = other.thread(t["id"])
    assert detail["accepted_reply_id"] == r["id"] and detail["accepted"] and detail["answered"]
    assert detail["replies"][0]["accepted"]
    assert asker.post(url, {"reply_id": None}).json() == {"accepted_reply_id": None}
    # Deleting the accepted reply takes the acceptance back.
    asker.post(url, {"reply_id": r["id"]})
    other.delete(f"/commons/replies/{r['id']}")
    assert asker.thread(t["id"])["accepted_reply_id"] is None


def test_follow_writes_the_profile(c: CommonsEnv) -> None:
    asker, fan = c.user(), c.user()
    t = asker.ask("Any advice on a quantum computing lab?")
    url = f"/commons/threads/{t['id']}/follow"
    assert fan.post(url, {"follow": True}).json() == {"following": True}
    assert fan.post(url, {"follow": True}).json() == {"following": True}
    assert fan.thread(t["id"])["following"] and not asker.thread(t["id"])["following"]
    with c.env.db() as db:
        profile = db.get(m.StudentProfile, uuid.UUID(fan.account_id))
        assert profile is not None and profile.follows["threads"] == [t["id"]]
    assert fan.post(url, {"follow": False}).json() == {"following": False}
    with c.env.db() as db:
        profile = db.get(m.StudentProfile, uuid.UUID(fan.account_id))
        assert profile is not None and profile.follows["threads"] == []
    assert fan.post("/commons/threads/999999/follow", {"follow": True}).status_code == 404


def test_presence_counts_others_but_not_yourself(c: CommonsEnv) -> None:
    a, b = c.user(), c.user()
    t = a.ask("Which Hum sequence has the least lecture?")
    url = f"/commons/threads/{t['id']}"
    assert a.post(f"{url}/typing").status_code == 204
    assert a.post(f"{url}/typing").status_code == 204  # twice is still one typer
    assert a.get(f"{url}/presence").json()["typing"] == 0
    assert b.get(f"{url}/presence").json()["typing"] == 1
    assert c.anon().get(f"{url}/presence").json()["typing"] == 1
    b.post(f"{url}/typing")
    assert a.get(f"{url}/presence").json()["typing"] == 1
    assert c.anon().get(f"{url}/presence").json()["typing"] == 2
    reply = b.reply(t["id"], "Media Aesthetics, maybe?")["reply"]
    p = a.get(f"{url}/presence").json()
    assert p["latest_reply_id"] == reply["id"] and p["reply_count"] == 1 and p["score"] == 0
    # Keys hold only hashes and expire: drop one and it stops counting.
    keys = [k for k in c.env.redis.keys("commons:typing:*") if k.count(":") == 3]
    assert len(keys) == 2
    commons = [k for k in c.env.redis.keys("commons:*")]
    assert not any(
        a.account_id
        in f"{k}={c.env.redis.get(k) if c.env.redis.type(k) == 'string' else c.env.redis.smembers(k)}"
        for k in commons
    )
    c.env.redis.delete(keys[0])
    assert c.anon().get(f"{url}/presence").json()["typing"] == 1
    assert all(c.env.redis.ttl(k) <= 8 for k in keys[1:])


def test_reports(c: CommonsEnv) -> None:
    asker, other = c.user(), c.user()
    t = asker.ask("Is CMSC 14100 OK with no programming background?")
    r = other.reply(t["id"], "rude words")["reply"]
    first = asker.post(
        "/commons/reports",
        {"target_type": "reply", "target_id": r["id"], "reason": "Rude: mail x@y.edu"},
    )
    assert first.status_code == 202
    again = asker.post(
        "/commons/reports", {"target_type": "reply", "target_id": r["id"], "reason": "again"}
    )
    assert again.json()["id"] == first.json()["id"]
    assert (
        other.post(
            "/commons/reports", {"target_type": "thread", "target_id": t["id"], "reason": "spam"}
        ).status_code
        == 202
    )
    assert (
        other.post(
            "/commons/reports", {"target_type": "thread", "target_id": 999999, "reason": "x"}
        ).status_code
        == 404
    )
    with c.env.db() as db:
        rows = db.scalars(sa.select(m.CommonsReport).order_by(m.CommonsReport.id)).all()
        assert len(rows) == 2 and "x@y.edu" not in rows[0].reason
        assert rows[0].reporter_ref == commons_ref(uuid.UUID(asker.account_id), t["id"])


def test_rate_limits_and_suspensions(c: CommonsEnv, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commons_router, "THREADS_PER_HOUR", Limit("commons-thread-test", 2, HOUR))
    u = c.user()
    u.ask("First question title")
    u.ask("Second question title")
    third = u.post("/commons/threads", {"title": "Third question title"})
    assert third.status_code == 429 and "Retry-After" in third.headers
    banned = c.user()
    with c.env.db() as db:
        db.execute(
            sa.update(m.Account)
            .where(m.Account.id == uuid.UUID(banned.account_id))
            .values(status="banned")
        )
        db.commit()
    assert banned.post("/commons/threads", {"title": "A banned question"}).status_code == 403
    assert banned.get("/commons/threads").status_code == 200


# -------------------------------------------------------------------- account export/delete


def _two_users_talking(
    c: CommonsEnv,
) -> tuple[Any, Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    leaver, stayer = c.user("leaver"), c.user("stayer")
    own = leaver.ask(
        "Leaver's question about CMSC 14100", body_md="details", course_code="CMSC 14100"
    )
    other = stayer.ask("Stayer's question about MATH 15300")
    answered = leaver.reply(other["id"], "Leaver answers")["reply"]
    stayer.reply(other["id"], "Stayer replies to the leaver", parent=answered["id"])
    leaf = leaver.reply(other["id"], "Leaver's leaf")["reply"]
    stayer.reply(own["id"], "Stayer answers the leaver")
    leaver.post("/commons/votes", {"target_type": "thread", "target_id": other["id"], "value": 1})
    leaver.post(
        "/commons/reports", {"target_type": "thread", "target_id": other["id"], "reason": "dup"}
    )
    return leaver, stayer, own, other, {"answered": answered, "leaf": leaf}


def test_export_commons(c: CommonsEnv) -> None:
    leaver, _, own, other, replies = _two_users_talking(c)
    with c.env.db() as db:
        data = export_commons(db, uuid.UUID(leaver.account_id))
    assert [t["id"] for t in data["threads"]] == [own["id"]]
    assert data["threads"][0]["course"] == "CMSC 14100"
    assert {r["id"] for r in data["replies"]} == {replies["answered"]["id"], replies["leaf"]["id"]}
    assert data["votes"] == [{"target_type": "thread", "target_id": other["id"], "value": 1}]
    assert data["reports"][0]["reason"] == "dup"
    with c.env.db() as db:
        assert export_commons(db, uuid.uuid4()) == {
            "threads": [],
            "replies": [],
            "votes": [],
            "reports": [],
        }


def test_forget_commons_keep(c: CommonsEnv) -> None:
    leaver, stayer, own, other, _ = _two_users_talking(c)
    with c.env.db() as db:
        forget_commons(db, uuid.UUID(leaver.account_id), "keep")
        db.commit()
    detail = stayer.thread(own["id"])
    assert detail["handle"] == "[deleted account]"
    handles = [r["handle"] for r in walk(stayer.thread(other["id"])["replies"])]
    assert handles.count("[deleted account]") == 2
    with c.env.db() as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(m.CommonsVote)) == 0
        assert db.scalar(sa.select(m.CommonsReport.reporter_ref)) is None


def test_forget_commons_delete(c: CommonsEnv) -> None:
    leaver, stayer, own, other, replies = _two_users_talking(c)
    with c.env.db() as db:
        forget_commons(db, uuid.UUID(leaver.account_id), "delete")
        db.commit()
    assert stayer.get(f"/commons/threads/{own['id']}").status_code == 404
    detail = stayer.thread(other["id"])
    tree = list(walk(detail["replies"]))
    assert replies["leaf"]["id"] not in {r["id"] for r in tree}  # a leaf is deleted
    tomb = next(r for r in tree if r["id"] == replies["answered"]["id"])  # kept for its child
    assert tomb["status"] == "deleted" and tomb["children"]
    assert detail["reply_count"] == 1
    with c.env.db() as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(m.CommonsVote)) == 0
        refs = service.thread_refs(db, uuid.UUID(leaver.account_id))
        left = db.scalars(
            sa.select(m.CommonsReply.id).where(m.CommonsReply.author_ref.in_(list(refs)))
        )
        assert list(left) == []
