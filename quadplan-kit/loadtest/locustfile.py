"""Load test (prompt 12): POST /verify at 50 requests/second (p95 under 500 ms) and forum page
reads at 100 requests/second.

Run against a local stack (never a shared or production server):

    make loadtest            # both scenarios, 60 s each, against http://localhost:8000

Each /verify request sends a full four-year plan from `plans.json` plus one or two random
extra electives, so almost every request is a new plan (a cache miss), like a student
editing. Forum reads log in once as LOAD_LOGIN / LOAD_PASSWORD and share that session.
The users are FastHttpUser: locust's default client tops out near 100 requests/second on a
laptop and then measures its own queueing, not the server. Each user starts at a random
moment within its first second: users that all fire on the same tick send the whole second's
load as one burst (median 750 ms instead of 10 ms on the same server), which no real
traffic does.
"""

from __future__ import annotations

import copy
import json
import os
import random
from pathlib import Path
from typing import Any

import gevent
from locust import FastHttpUser, constant_throughput, events, tag, task

DATA = json.loads((Path(__file__).parent / "plans.json").read_text())
PLANS: list[dict[str, Any]] = DATA["plans"]
ELECTIVES: list[str] = DATA["electives"]
TERMS = ["2026-AU", "2027-WI", "2027-SP", "2027-AU", "2028-WI", "2028-SP", "2028-AU", "2029-WI"]
SESSION: dict[str, Any] = {}


def a_new_plan() -> dict[str, Any]:
    plan = copy.deepcopy(random.choice(PLANS))
    for _ in range(random.randint(1, 2)):
        plan["items"].append({"course": random.choice(ELECTIVES), "term": random.choice(TERMS)})
    return plan


@events.test_start.add_listener
def log_in(environment: Any, **_: Any) -> None:
    """One login for every forum reader (logins are rate-limited per address). The session
    cookie is sent as a header: it is a Secure cookie, which clients drop over plain http."""
    login, password = os.environ.get("LOAD_LOGIN"), os.environ.get("LOAD_PASSWORD")
    if not (login and password) or environment.host is None:
        return
    import requests

    host = environment.host.rstrip("/")
    resp = requests.post(
        f"{host}/auth/login", json={"login": login, "password": password}, timeout=30
    )
    resp.raise_for_status()
    SESSION["cookie"] = "; ".join(f"{k}={v}" for k, v in resp.cookies.items())
    headers = {"Cookie": SESSION["cookie"]}
    SESSION["page_ids"] = [
        p["page_id"]
        for code in ("CMSC 14100", "MATH 15100", "ECON 20000")
        for p in requests.get(f"{host}/forum/courses/{code}", headers=headers, timeout=30)
        .json()
        .get("pages", [])
    ] or [1]


def stagger() -> None:
    gevent.sleep(random.random())


class Verifier(FastHttpUser):
    """50 of these at one request per second each = 50 requests/second."""

    wait_time = constant_throughput(1)

    def on_start(self) -> None:
        stagger()

    @tag("verify")
    @task
    def verify(self) -> None:
        self.client.post("/verify", json={"plan": a_new_plan()}, name="POST /verify")


class ForumReader(FastHttpUser):
    """100 of these at one request per second each = 100 requests/second."""

    wait_time = constant_throughput(1)

    def on_start(self) -> None:
        stagger()
        self.headers = {"Cookie": SESSION.get("cookie", "")}

    @tag("forum")
    @task(2)
    def page(self) -> None:
        page = random.choice(SESSION.get("page_ids", [1]))
        self.client.get(f"/forum/pages/{page}", name="GET /forum/pages/{id}", headers=self.headers)

    @tag("forum")
    @task(1)
    def posts(self) -> None:
        page = random.choice(SESSION.get("page_ids", [1]))
        self.client.get(
            f"/forum/pages/{page}/posts?sort=best",
            name="GET /forum/pages/{id}/posts",
            headers=self.headers,
        )
