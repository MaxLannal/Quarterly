"""`/account`: export, change password, delete (SPEC "Account deletion")."""

import datetime as dt
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from api.auth.hashing import author_ref
from api.db import models as m
from auth_test_support import PASSWORD, Env, auth_env, csrf, migrated_database
from sqlalchemy import select, text

pytestmark = pytest.mark.db

EMAIL = "quiet-heron@uchicago.edu"


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    with auth_env(db_url, monkeypatch) as e:
        yield e


def seed_catalog(env: Env) -> dict[str, int]:
    """One catalog year, two courses, one instructor, two forum pages."""
    with env.db() as db:
        db.add(m.CatalogYear(id="2099-00"))
        db.flush()
        courses = [
            m.Course(catalog_year="2099-00", subject="TEST", number=n, code=f"TEST {n}", title=n)
            for n in ("10100", "10200")
        ]
        instructor = m.Instructor(slug="jane-doe", display_name="Jane Doe")
        db.add_all([*courses, instructor])
        db.flush()
        pages = [m.CourseInstructor(course_id=c.id, instructor_id=instructor.id) for c in courses]
        db.add_all(pages)
        db.commit()
        return {
            "course_a": courses[0].id,
            "course_b": courses[1].id,
            "page_a": pages[0].id,
            "page_b": pages[1].id,
        }


def add_plan(env: Env, account_id: str, ids: dict[str, int], name: str = "Main plan") -> uuid.UUID:
    with env.db() as db:
        plan = m.Plan(
            account_id=uuid.UUID(account_id),
            name=name,
            catalog_year="2099-00",
            entry_term="2099-AU",
            placements=["TEST 10100"],
            overload_reasons={},
            is_primary=True,
        )
        db.add(plan)
        db.flush()
        db.add_all(
            [
                m.PlanItem(plan_id=plan.id, course_id=ids["course_a"], term_id="2099-AU"),
                m.PlanItem(
                    plan_id=plan.id,
                    course_id=ids["course_b"],
                    term_id="2100-WI",
                    status="completed",
                    locked=True,
                    grade="A-",
                ),
                m.PlanItem(plan_id=plan.id, slot_ref="test-bs/electives/1", term_id="2100-SP"),
                m.Credit(plan_id=plan.id, kind="AP", label="AP Calculus BC", units=100),
                m.Goal(
                    plan_id=plan.id,
                    goal_key="light-first",
                    scope="term",
                    term_id="2099-AU",
                    type="light_quarter",
                    params={"max_courses": 3},
                    hard=True,
                ),
                m.Goal(
                    plan_id=plan.id,
                    goal_key="grad",
                    scope="career",
                    type="graduate_by",
                    params={"by_term": "Y4-SP"},
                ),
            ]
        )
        db.commit()
        return plan.id


# -------------------------------------------------------------------------------- export


def test_export_requires_login(env: Env) -> None:
    assert env.client.get("/account/export").status_code == 401


def test_export_returns_the_account_and_its_plans(env: Env) -> None:
    ids = seed_catalog(env)
    session = env.signup("quiet-heron", EMAIL)
    other = env.signup("other-user", "other@uchicago.edu", client=env.browser())
    plan_id = add_plan(env, session["account"]["id"], ids)
    add_plan(env, other["account"]["id"], ids, name="Someone else's plan")

    resp = env.client.get("/account/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["cache-control"] == "no-store"
    body = resp.json()
    assert body["account"] == session["account"]
    assert "@" not in resp.text and "password" not in resp.text  # no email, no hash
    (plan,) = body["plans"]
    assert plan["id"] == str(plan_id) and plan["name"] == "Main plan" and plan["is_primary"]
    assert plan["catalog_year"] == "2099-00" and plan["entry_term"] == "2099-AU"
    assert plan["plan_hash"].startswith("sha256:")
    state = plan["state"]
    assert state["placements"] == ["TEST 10100"]
    items = [(i["course"], i["slot_ref"], i["term"], i["status"]) for i in state["items"]]
    assert items == [
        ("TEST 10100", None, "2099-AU", "planned"),
        ("TEST 10200", None, "2100-WI", "completed"),
        (None, "test-bs/electives/1", "2100-SP", "planned"),
    ]
    assert state["items"][1]["locked"] is True and state["items"][1]["grade"] == "A-"
    assert state["credits"] == [
        {"kind": "AP", "label": "AP Calculus BC", "maps_to": None, "units": 100}
    ]
    goals = {g["id"]: g for g in state["goals"]}
    assert goals["light-first"]["type"] == "light_quarter"
    assert goals["light-first"]["max_courses"] == 3 and goals["light-first"]["hard"] is True
    assert goals["grad"]["by_term"] == "Y4-SP"


def test_export_with_no_plans(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    assert env.client.get("/account/export").json()["plans"] == []


# ----------------------------------------------------------------------- change password


def test_change_password(env: Env) -> None:
    session = env.signup("quiet-heron", EMAIL)
    phone = env.browser()
    assert phone.post("/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 200
    new = "a brand new password"

    wrong = env.client.post(
        "/account/password",
        json={"current_password": "not-my-password", "new_password": new},
        headers=csrf(session),
    )
    assert wrong.status_code == 403
    short = env.client.post(
        "/account/password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=csrf(session),
    )
    assert short.status_code == 422
    ok = env.client.post(
        "/account/password",
        json={"current_password": PASSWORD, "new_password": new},
        headers=csrf(session),
    )
    assert ok.status_code == 204
    # This browser stays logged in; the other session is ended.
    assert env.client.get("/auth/session").status_code == 200
    assert phone.get("/auth/session").status_code == 401
    fresh = env.browser()
    assert fresh.post("/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 401
    assert fresh.post("/auth/login", json={"login": EMAIL, "password": new}).status_code == 200
    with env.db() as db:
        assert db.scalars(select(m.Account.password_hash)).one().startswith("$argon2id$")  # type: ignore[union-attr]


def test_password_endpoints_require_login(env: Env) -> None:
    body = {"current_password": PASSWORD, "new_password": "a brand new password"}
    assert env.client.post("/account/password", json=body).status_code == 401
    assert (
        env.client.post("/account/delete", json={"password": PASSWORD, "posts": "keep"}).status_code
        == 401
    )


def test_password_confirmation_attempts_are_limited(env: Env) -> None:
    session = env.signup("quiet-heron", EMAIL)
    body = {"password": "not-my-password", "posts": "keep"}
    for _ in range(10):
        resp = env.client.post("/account/delete", json=body, headers=csrf(session))
        assert resp.status_code == 403
    locked = env.client.post(
        "/account/delete", json={"password": PASSWORD, "posts": "keep"}, headers=csrf(session)
    )
    assert locked.status_code == 429
    assert env.client.get("/auth/session").status_code == 200  # nothing was deleted


def test_password_confirmation_is_counted_before_the_password_is_checked(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.routers import account as account_router

    session = env.signup("quiet-heron", EMAIL)
    seen: list[list[str]] = []
    real = account_router.verify_password

    def spy(stored: str | None, password: str) -> bool:
        seen.append([env.redis.get(k) for k in env.redis.keys("rl:password-fail:*")])
        return real(stored, password)

    monkeypatch.setattr(account_router, "verify_password", spy)
    body = {"current_password": "not-my-password", "new_password": "a brand new password"}
    assert env.client.post("/account/password", json=body, headers=csrf(session)).status_code == 403
    assert seen[-1] == ["1"]
    body["current_password"] = PASSWORD
    assert env.client.post("/account/password", json=body, headers=csrf(session)).status_code == 204
    assert seen[-1] == ["2"]
    # The good attempt was given back; the wrong one stays counted.
    assert [env.redis.get(k) for k in env.redis.keys("rl:password-fail:*")] == ["1"]


# -------------------------------------------------------------------------------- delete


@pytest.mark.parametrize(
    ("status", "suspended_days", "allowed"),
    [
        ("banned", None, False),
        ("suspended", None, False),
        ("active", 1, False),
        ("active", 30, False),
        ("active", 0, True),  # the suspension ended today
        ("active", -3, True),
    ],
)
def test_a_banned_or_suspended_account_cannot_be_deleted(
    env: Env, status: str, suspended_days: int | None, allowed: bool
) -> None:
    session = env.signup("quiet-heron", EMAIL)
    today = dt.datetime.now(dt.UTC).date()
    until = None if suspended_days is None else today + dt.timedelta(days=suspended_days)
    with env.db() as db:
        account = db.scalars(select(m.Account)).one()
        account.status, account.suspended_until = status, until
        db.commit()
    resp = env.client.post(
        "/account/delete", json={"password": PASSWORD, "posts": "delete"}, headers=csrf(session)
    )
    with env.db() as db:
        remaining = db.scalars(select(m.Account.email)).all()
    if allowed:
        assert resp.status_code == 204 and remaining == []
    else:
        assert resp.status_code == 409 and remaining == [EMAIL]
        # The email is still taken, so the ban cannot be escaped by signing up again.
        assert env.client.get("/auth/session").status_code == 200


def seed_forum(env: Env, me: str, them: str, ids: dict[str, int]) -> dict[str, Any]:
    """`me` posts on two pages and comments on someone else's post; `them` replies to one of
    my comments and comments on my post."""
    mine, theirs = uuid.UUID(me), uuid.UUID(them)
    a, b = ids["page_a"], ids["page_b"]
    with env.db() as db:
        my_a = m.Pseudonym(author_ref=author_ref(mine, a), course_instructor_id=a, handle="heron")
        my_b = m.Pseudonym(author_ref=author_ref(mine, b), course_instructor_id=b, handle="otter")
        their_a = m.Pseudonym(
            author_ref=author_ref(theirs, a), course_instructor_id=a, handle="fox"
        )
        db.add_all([my_a, my_b, their_a])
        db.flush()
        my_review = m.Post(
            course_instructor_id=a,
            kind="review",
            author_ref=my_a.author_ref,
            pseudonym_id=my_a.id,
            body_md="My review",
            term_taken="2099-AU",
        )
        my_thread = m.Post(
            course_instructor_id=b,
            kind="discussion",
            author_ref=my_b.author_ref,
            pseudonym_id=my_b.id,
            title="Q",
            body_md="My question",
        )
        their_post = m.Post(
            course_instructor_id=a,
            kind="discussion",
            author_ref=their_a.author_ref,
            pseudonym_id=their_a.id,
            title="T",
            body_md="Their thread",
        )
        db.add_all([my_review, my_thread, their_post])
        db.flush()
        db.add(
            m.ReviewRating(
                post_id=my_review.id,
                overall=4,
                difficulty=3,
                intellectual_intensity=4,
                workload_hours=10,
                would_recommend=True,
            )
        )

        def comment(
            post: m.Post, ref: str, pseud: m.Pseudonym, body: str, parent: m.Comment | None = None
        ) -> m.Comment:
            row = m.Comment(
                post_id=post.id,
                parent_id=parent.id if parent else None,
                path="x",
                author_ref=ref,
                pseudonym_id=pseud.id,
                body_md=body,
            )
            db.add(row)
            db.flush()
            row.path = f"{parent.path}.{row.id}" if parent else str(row.id)
            return row

        replied = comment(their_post, my_a.author_ref, my_a, "My comment with a reply")
        reply = comment(their_post, their_a.author_ref, their_a, "Their reply", replied)
        leaf = comment(their_post, my_a.author_ref, my_a, "My leaf comment")
        chain = comment(their_post, my_a.author_ref, my_a, "My own follow-up", leaf)
        on_mine = comment(my_review, their_a.author_ref, their_a, "Their comment on my review")
        db.add_all(
            [
                m.Vote(
                    voter_ref=my_a.author_ref, target_type="post", target_id=their_post.id, value=1
                ),
                m.Vote(
                    voter_ref=their_a.author_ref,
                    target_type="post",
                    target_id=my_review.id,
                    value=1,
                ),
                m.Report(
                    target_type="post",
                    target_id=their_post.id,
                    reason="spam",
                    reporter_ref=my_a.author_ref,
                ),
            ]
        )
        db.commit()
        return {
            "my_posts": [my_review.id, my_thread.id],
            "their_post": their_post.id,
            "replied": replied.id,
            "reply": reply.id,
            "leaf": leaf.id,
            "chain": chain.id,
            "on_mine": on_mine.id,
            "my_refs": {my_a.author_ref, my_b.author_ref},
            "their_ref": their_a.author_ref,
        }


def setup_two_accounts(env: Env) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ids = seed_catalog(env)
    me = env.signup("quiet-heron", EMAIL)
    them = env.signup("other-user", "other@uchicago.edu", client=env.browser())
    add_plan(env, me["account"]["id"], ids)
    add_plan(env, them["account"]["id"], ids, name="Theirs")
    forum = seed_forum(env, me["account"]["id"], them["account"]["id"], ids)
    return me, them, forum


def assert_account_erased(env: Env, forum: dict[str, Any]) -> None:
    with env.db() as db:
        assert db.scalars(select(m.Account.username)).all() == ["other-user"]
        assert EMAIL not in str(db.execute(text("SELECT * FROM account")).all())
        assert db.scalars(select(m.Plan.name)).all() == ["Theirs"]
        assert db.scalar(select(m.PlanItem.id).join(m.Plan).where(m.Plan.name != "Theirs")) is None
        assert (
            db.scalars(select(m.Goal.plan_id).distinct()).all()
            == db.scalars(select(m.Plan.id)).all()
        )
        # Nothing in the forum can be tied to the account any more.
        refs = forum["my_refs"]
        assert not refs & set(db.scalars(select(m.Post.author_ref)).all())
        assert not refs & set(db.scalars(select(m.Comment.author_ref)).all())
        assert not refs & set(db.scalars(select(m.Pseudonym.author_ref)).all())
        assert db.scalars(select(m.Vote.voter_ref)).all() == [forum["their_ref"]]
        assert db.scalars(select(m.Report.reporter_ref)).all() == [None]
        # The other student's content is untouched.
        assert db.get(m.Post, forum["their_post"]).author_ref == forum["their_ref"]  # type: ignore[union-attr]
        assert db.get(m.Comment, forum["reply"]).body_md == "Their reply"  # type: ignore[union-attr]
        assert db.scalars(select(m.Pseudonym.handle)).all() == ["fox"]


def test_delete_needs_the_password(env: Env) -> None:
    me, _, _ = setup_two_accounts(env)
    resp = env.client.post(
        "/account/delete", json={"password": "not-my-password", "posts": "delete"}, headers=csrf(me)
    )
    assert resp.status_code == 403
    assert (
        env.client.post(
            "/account/delete", json={"password": PASSWORD, "posts": "maybe"}, headers=csrf(me)
        ).status_code
        == 422
    )
    with env.db() as db:
        assert len(db.scalars(select(m.Account.id)).all()) == 2
        assert len(db.scalars(select(m.Post.id)).all()) == 3


def test_delete_account_keeping_posts_as_deleted_account(env: Env) -> None:
    me, them, forum = setup_two_accounts(env)
    phone = env.browser()
    assert phone.post("/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 200

    resp = env.client.post(
        "/account/delete", json={"password": PASSWORD, "posts": "keep"}, headers=csrf(me)
    )
    assert resp.status_code == 204, resp.text
    assert "max-age=0" in resp.headers["set-cookie"].lower()
    # Sessions are gone everywhere, and the login no longer exists.
    assert env.client.get("/auth/session").status_code == 401
    assert phone.get("/auth/session").status_code == 401
    assert env.redis.keys(f"sess-index:{me['account']['id']}") == []
    assert phone.post("/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 401

    assert_account_erased(env, forum)
    with env.db() as db:
        # Posts and comments remain, authorless: shown as "[deleted account]".
        for post_id in forum["my_posts"]:
            post = db.get(m.Post, post_id)
            assert post is not None and post.author_ref is None and post.pseudonym_id is None
        assert db.get(m.Post, forum["my_posts"][0]).body_md == "My review"  # type: ignore[union-attr]
        assert db.scalar(select(m.ReviewRating.overall)) == 4
        for key in ("replied", "leaf", "chain"):
            comment = db.get(m.Comment, forum[key])
            assert comment is not None and comment.author_ref is None
            assert comment.body_md.startswith("My ")
        assert len(db.scalars(select(m.Comment.id)).all()) == 5

    # The email is free again: the student can sign up afresh.
    again = env.signup("quiet-heron", EMAIL, client=env.browser())
    assert again["account"]["id"] != me["account"]["id"]
    assert them["account"]["username"] == "other-user"


def test_delete_account_deleting_posts(env: Env) -> None:
    me, _, forum = setup_two_accounts(env)
    resp = env.client.post(
        "/account/delete", json={"password": PASSWORD, "posts": "delete"}, headers=csrf(me)
    )
    assert resp.status_code == 204, resp.text
    assert env.client.get("/auth/session").status_code == 401

    assert_account_erased(env, forum)
    with env.db() as db:
        # My posts are gone, with the rating and the comments under them.
        assert db.scalars(select(m.Post.id)).all() == [forum["their_post"]]
        assert db.scalars(select(m.ReviewRating.post_id)).all() == []
        assert db.get(m.Comment, forum["on_mine"]) is None
        # My comments without replies from others are gone (including my own chain) ...
        assert db.get(m.Comment, forum["leaf"]) is None
        assert db.get(m.Comment, forum["chain"]) is None
        # ... the one somebody replied to is blanked so the reply survives.
        replied = db.get(m.Comment, forum["replied"])
        assert replied is not None and replied.body_md == "[deleted]"
        assert replied.author_ref is None and replied.pseudonym_id is None
        assert db.get(m.Comment, forum["reply"]) is not None


def test_delete_account_without_any_forum_activity(env: Env) -> None:
    me = env.signup("quiet-heron", EMAIL)
    resp = env.client.post(
        "/account/delete", json={"password": PASSWORD, "posts": "delete"}, headers=csrf(me)
    )
    assert resp.status_code == 204
    with env.db() as db:
        assert db.scalars(select(m.Account.id)).all() == []
