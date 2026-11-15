"""Load test (prompt 12): POST /verify at 50 requests/second (p95 under 500 ms) and forum page
reads at 100 requests/second.

Run against a local stack (never a shared or production server):

    make loadtest            # both scenarios, 60 s each, against http://localhost:8000

Each /verify request sends a full four-year plan from `plans.json` plus one or two random
extra electives, so almost every request is a new plan (a cache miss), like a student
editing. Forum reads log in once as LOAD_LOGIN / LOAD_PASSWORD and share that session.
"""

from __future__ import annotations

import copy
import json
import os
import random
from pathlib import Path
from typing import Any

from locust import HttpUser, constant_throughput, events, tag, task

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
    """One login for every forum reader (logins are rate-limited per address)."""
    login, password = os.environ.get("LOAD_LOGIN"), os.environ.get("LOAD_PASSWORD")
    if not (login and password) or environment.host is None:
        return
    import httpx

    with httpx.Client(base_url=environment.host) as client:
        resp = client.post("/auth/login", json={"login": login, "password": password})
        resp.raise_for_status()
        SESSION["cookies"] = dict(client.cookies)
        SESSION["page_ids"] = [
            p["page_id"]
            for code in ("CMSC 14100", "MATH 15100", "ECON 20000")
            for p in client.get(f"/forum/courses/{code}").json().get("pages", [])
        ] or [1]


class Verifier(HttpUser):
    """50 of these at one request per second each = 50 requests/second."""

    wait_time = constant_throughput(1)

    @tag("verify")
    @task
    def verify(self) -> None:
        self.client.post("/verify", json={"plan": a_new_plan()}, name="POST /verify")


class ForumReader(HttpUser):
    """100 of these at one request per second each = 100 requests/second."""

    wait_time = constant_throughput(1)

    def on_start(self) -> None:
        for name, value in SESSION.get("cookies", {}).items():
            self.client.cookies.set(name, value)

    @tag("forum")
    @task(2)
    def page(self) -> None:
        page = random.choice(SESSION.get("page_ids", [1]))
        self.client.get(f"/forum/pages/{page}", name="GET /forum/pages/{id}")

    @tag("forum")
    @task(1)
    def posts(self) -> None:
        page = random.choice(SESSION.get("page_ids", [1]))
        self.client.get(f"/forum/pages/{page}/posts?sort=best", name="GET /forum/pages/{id}/posts")
