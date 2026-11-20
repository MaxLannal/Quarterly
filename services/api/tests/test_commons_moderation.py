"""Moderating the Commons (OPEN_QUESTIONS CC-7): reported questions and replies reach the admin's
queue; removing one shows "[removed]" (replies under it stay), keeping one closes its reports."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from api.db import models as m
from auth_test_support import migrated_database
from test_commons_support import CommonsEnv, User, commons_env

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def c(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[CommonsEnv]:
    with commons_env(db_url, monkeypatch) as cenv:
        yield cenv


def admin(c: CommonsEnv) -> User:
    user = c.user("the-admin")
    with c.env.db() as db:
        db.execute(
            sa.update(m.Account).where(m.Account.username == "the-admin").values(role="admin")
        )
        db.commit()
    return user


def report(user: User, target_type: str, target_id: int, reason: str) -> None:
    body = {"target_type": target_type, "target_id": target_id, "reason": reason}
    assert user.post("/commons/reports", body).status_code == 202


def test_only_admins_see_the_queue(c: CommonsEnv) -> None:
    student = c.user()
    assert student.get("/admin/commons-reports").status_code == 403
    assert c.anon().get("/admin/commons-reports").status_code == 401


def test_a_reported_question_is_removed_and_its_reports_close(c: CommonsEnv) -> None:
    asker, other = c.user(), c.user()
    t = asker.ask("Is CMSC 14100 OK with no programming background?")
    reply = other.reply(t["id"], "Try the placement page first.")["reply"]
    report(other, "thread", t["id"], "Off topic")
    report(c.user(), "thread", t["id"], "Spam")
    boss = admin(c)
    queue = boss.get("/admin/commons-reports").json()
    item = next(i for i in queue if i["target_type"] == "thread" and i["target_id"] == t["id"])
    assert {r["reason"] for r in item["reports"]} == {"Off topic", "Spam"}
    assert item["href"] == f"/forum/t/{t['id']}" and not item["by_ai"]
    out = boss.post(
        f"/admin/commons-reports/thread/{t['id']}/decision", {"decision": "remove", "note": "spam"}
    ).json()
    assert out == {
        "target_type": "thread",
        "target_id": t["id"],
        "status": "removed",
        "reports_closed": 2,
    }
    assert all(i["target_id"] != t["id"] for i in boss.get("/admin/commons-reports").json())
    assert c.anon().get(f"/commons/threads/{t['id']}").status_code == 404
    with c.env.db() as db:
        assert db.get(m.CommonsReply, reply["id"]) is not None  # replies under it stay
        action = db.scalar(
            sa.select(m.ModerationAction).where(m.ModerationAction.target_id == t["id"])
        )
        assert action is not None and action.target_type == "commons_thread"
        assert action.action == "remove" and action.actor == "admin"


def test_keeping_a_reply_closes_its_reports_and_leaves_it_visible(c: CommonsEnv) -> None:
    asker, other = c.user(), c.user()
    t = asker.ask("Which Hum sequence has the most discussion?")
    r = other.reply(t["id"], "Media Aesthetics is mostly discussion.")["reply"]
    report(asker, "reply", r["id"], "Not helpful")
    boss = admin(c)
    out = boss.post(f"/admin/commons-reports/reply/{r['id']}/decision", {"decision": "keep"})
    assert out.json()["status"] == "visible" and out.json()["reports_closed"] == 1
    assert all(i["target_id"] != r["id"] for i in boss.get("/admin/commons-reports").json())
    assert (
        boss.post("/admin/commons-reports/reply/999999/decision", {"decision": "keep"}).status_code
        == 404
    )
