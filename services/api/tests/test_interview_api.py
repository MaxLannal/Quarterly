"""The interviewing guide (`POST /agents/interview`) with FakeLLM and without a model: the topic
order, facts extracted from answers, follow-ups, progress, the portrait, grounding of the model's
facts in the student's own words, course mentions and the welcome-back greeting."""

from __future__ import annotations

from typing import Any

import pytest
from agent_test_support import events, of, use_llm
from api.agents import interview as iv
from auth_test_support import Env
from llm_gateway.api import FakeLLM, ToolCall
from test_profile_support import db_url_fixture, env_fixture, login  # noqa: F401

pytestmark = pytest.mark.db


def ask(
    env: Env,
    headers: dict[str, str],
    mode: str = "reply",
    message: str | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body = {"mode": mode, "message": message, "history": history or []}
    evs = events(env.client.post("/agents/interview", json=body, headers=headers))
    assert of(evs, "done"), evs
    turns = of(evs, "turn")
    assert len(turns) == 1, evs
    return turns[0]


def keep(env: Env, headers: dict[str, str], turn: dict[str, Any]) -> None:
    """The browser keeps every proposed fact."""
    proposed = {k: v for k, v in turn["proposed"].items() if v is not None}
    if proposed:
        resp = env.client.patch("/me/profile", json=proposed, headers=headers)
        assert resp.status_code == 200, resp.text


class Talk:
    """A conversation as the browser keeps it."""

    def __init__(self, env: Env, headers: dict[str, str]) -> None:
        self.env, self.headers = env, headers
        self.history: list[dict[str, Any]] = []
        self.last: dict[str, Any] = {}

    def start(self) -> dict[str, Any]:
        self.last = ask(self.env, self.headers, "start")
        self.history.append(
            {"role": "guide", "text": self.last["text"], "topic": self.last["topic"]}
        )
        return self.last

    def say(self, text: str, *, kept: bool = True) -> dict[str, Any]:
        turn = ask(self.env, self.headers, "reply", text, self.history)
        if kept:
            keep(self.env, self.headers, turn)
        self.history += [
            {"role": "student", "text": text},
            {"role": "guide", "text": turn["text"], "topic": turn["topic"]},
        ]
        self.last = turn
        return turn


# ------------------------------------------------------------------------------ no model


def test_the_rule_guide_walks_the_topics_and_ends_with_a_portrait(env: Env) -> None:
    headers = login(env)
    talk = Talk(env, headers)
    first = talk.start()
    assert first["topic"] == "class_year" and first["fallback"] is True
    assert first["progress"] == 0 and len(first["quick_replies"]) >= 3
    t = talk.say("I'm class of 2029")
    assert t["proposed"]["class_year"] == 2029 and t["topic"] == "interests"
    assert t["progress"] > first["progress"]
    t = talk.say("physics, film and Greek tragedy")
    assert t["proposed"]["interests"] == ["Physics", "Film", "Greek tragedy"]
    assert t["topic"] == "humanities" and "physics" in t["text"].lower()
    progress = t["progress"]
    t = talk.say("Enjoy specific topics")
    assert t["proposed"]["humanities_goal"] == "enjoy"
    assert t["topic"] == "humanities"  # a follow-up: which topics, specifically?
    assert "Greek tragedy" in t["quick_replies"]
    t = talk.say("Greek tragedy and philosophy of mind")
    assert t["proposed"]["humanities_topics"] == ["Greek tragedy", "Philosophy of mind"]
    assert t["topic"] == "research" and t["progress"] > progress
    t = talk.say("quantum materials")
    assert t["proposed"]["research_areas"] == ["Quantum materials"] and t["topic"] == "career"
    t = talk.say("A PhD and then research at a national lab")
    assert t["proposed"]["career_paths"] == ["Research / PhD"]
    assert t["proposed"]["career_plans"].startswith("A PhD") and t["topic"] == "future"
    t = talk.say("Quantum computing")
    assert t["topic"] == "future" and "algorithms" in t["text"]  # the user's example
    t = talk.say("The algorithms")
    assert "Quantum computing: algorithms" in t["proposed"]["future_domains"]
    assert t["topic"] == "constraints"
    t = talk.say("Balanced, and I work part-time")
    assert t["proposed"]["workload"] == "balanced"
    assert t["proposed"]["constraints"] == ["I work part-time"]
    assert t["topic"] == "wrapup" and t["done"] is True and t["progress"] == 1
    portrait = t["proposed"]["portrait"]
    assert portrait["headline"] and len(portrait["headline"]) <= 90
    assert "Physics" in portrait["themes"] and len(portrait["summary"]) <= 400
    assert t["quick_replies"] == ["Change something"]  # no routes to draft (issue #15)


def test_class_year_from_words_and_humanities_goal_from_keywords(env: Env) -> None:
    start = iv.academic_start()
    assert iv.class_year_from("I'm a first-year") == start + 4
    assert iv.class_year_from("sophomore") == start + 3
    assert iv.class_year_from("class of '28") == 2028
    assert iv.class_year_from("no idea") is None
    assert iv.goal_from("Just to pass") == "pass"
    assert iv.goal_from("I want to go deep") == "deep"
    assert iv.goal_from("a balance of both") == "balance"
    assert iv.goal_from("to enjoy some poetry") == "enjoy"
    headers = login(env)
    talk = Talk(env, headers)
    talk.start()
    t = talk.say("first-year!")
    assert t["proposed"]["class_year"] == start + 4


def test_not_sure_moves_on_and_counts_as_covered(env: Env) -> None:
    headers = login(env)
    talk = Talk(env, headers)
    talk.start()
    t = talk.say("Not sure yet")
    assert t["proposed"].get("class_year") is None and t["topic"] == "interests"
    assert t["progress"] > 0


def test_start_resumes_where_the_profile_left_off(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile",
        json={"class_year": 2029, "interests": ["Economics"], "humanities_goal": "pass"},
        headers=headers,
    )
    t = ask(env, headers, "start")
    assert t["topic"] == "research" and "Welcome back" in t["text"]
    assert t["progress"] == pytest.approx(round(3 / 7, 3))


def test_welcome_back_without_a_model_recalls_the_profile(env: Env) -> None:
    headers = login(env, "quiet-heron")
    env.client.patch(
        "/me/profile",
        json={
            "interests": ["Physics", "Film"],
            "future_domains": ["Quantum computing"],
            "portrait": {"headline": "A physicist with a film critic's eye"},
        },
        headers=headers,
    )
    t = ask(env, headers, "welcome_back")
    assert t["text"].startswith("Welcome back, quiet-heron.")
    assert "physics" in t["text"].lower() and "physicist with a film" in t["text"]
    assert "Draft my routes" not in t["quick_replies"] and t["proposed"] == {
        k: None for k in t["proposed"]
    }


# ------------------------------------------------------------------------------ with a model


def turn(text: str, topic: str = "interests", **facts: Any) -> dict[str, Any]:
    base = {
        "class_year": None,
        "interests": [],
        "research_areas": [],
        "humanities_goal": None,
        "humanities_topics": [],
        "humanities_note": None,
        "career_plans": None,
        "career_paths": [],
        "future_domains": [],
        "constraints": [],
        "workload": None,
    }
    return {
        "text": text,
        "quick_replies": ["Physics", "Film"],
        "topic": topic,
        "facts": {**base, **facts},
        "portrait": None,
        "done": False,
    }


def test_the_model_keeps_only_facts_the_student_said(env: Env) -> None:
    headers = login(env)
    env.client.patch("/me/profile", json={"interests": ["Physics"]}, headers=headers)
    fake = use_llm(
        env,
        FakeLLM(
            script={
                "a6_interview": [
                    [ToolCall("search_courses", {"query": "greek tragedy"})],
                    ToolCall(
                        "submit_turn",
                        turn(
                            "Greek tragedy and ML, lovely. UChicago has a course called "
                            "CLAS 21000. What do you want from the Humanities Core?",
                            topic="humanities",
                            interests=["Greek tragedy", "Machine learning", "Opera"],
                            class_year=2031,
                            workload="intense",
                        ),
                    ),
                ]
            }
        ),
    )
    history = [{"role": "guide", "text": "What pulls at you?", "topic": "interests"}]
    evs = events(
        env.client.post(
            "/agents/interview",
            json={"mode": "reply", "message": "greek tragedy and ML", "history": history},
            headers=headers,
        )
    )
    steps = of(evs, "step")
    assert [s["status"] for s in steps] == ["started", "done"]
    assert steps[0]["tool"] == "search_courses"
    t = of(evs, "turn")[0]
    assert t["fallback"] is False and t["topic"] == "humanities"
    # Merged with the profile; "Opera" (never said), the class year and the workload dropped.
    assert t["proposed"]["interests"] == ["Physics", "Greek tragedy", "Machine learning"]
    assert t["proposed"]["class_year"] is None and t["proposed"]["workload"] is None
    assert t["courses"] == [{"code": "CLAS 21000", "title": "Greek Tragedy"}]
    assert t["progress"] > 0 and of(evs, "done")[0]["fallback"] is False
    first = fake.calls[0]["messages"][0]["content"]
    assert '<untrusted_source id="answer">' in first and "greek tragedy and ML" in first


def test_an_invented_course_gets_one_repair_then_the_rules_take_over(env: Env) -> None:
    headers = login(env)
    use_llm(
        env,
        FakeLLM(
            script={
                "a6_interview": [
                    ToolCall("submit_turn", turn("Try PHYS 99999! Which class are you in?")),
                    ToolCall("submit_turn", turn("Still PHYS 99999. Which class?")),
                ]
            }
        ),
    )
    t = ask(env, headers, "start")
    assert t["fallback"] is True and "PHYS 99999" not in t["text"]
    assert t["topic"] == "class_year"


def test_a_portrait_at_wrapup_and_done(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile",
        json={
            "class_year": 2029,
            "interests": ["Physics"],
            "research_areas": ["Lasers"],
            "humanities_goal": "pass",
            "career_paths": ["Industry"],
            "future_domains": ["Quantum computing"],
        },
        headers=headers,
    )
    payload = turn("Thank you! Here's your portrait.", topic="wrapup", workload="balanced")
    payload["portrait"] = {
        "headline": "A physicist heading for the quantum",
        "summary": "You love physics and want the Core done efficiently.",
        "themes": ["Physics", "Quantum computing", "Lasers"],
    }
    payload["done"] = True
    use_llm(env, FakeLLM(script={"a6_interview": [ToolCall("submit_turn", payload)]}))
    history = [{"role": "guide", "text": "How heavy should quarters be?", "topic": "constraints"}]
    evs = events(
        env.client.post(
            "/agents/interview",
            json={"mode": "reply", "message": "balanced please", "history": history},
            headers=headers,
        )
    )
    t = of(evs, "turn")[0]
    assert t["done"] is True and t["progress"] == 1 and t["topic"] == "wrapup"
    assert t["proposed"]["workload"] == "balanced"
    assert t["proposed"]["portrait"]["headline"] == "A physicist heading for the quantum"


def test_welcome_back_is_cached_per_profile(env: Env) -> None:
    headers = login(env)
    env.client.patch("/me/profile", json={"interests": ["Film"]}, headers=headers)
    fake = use_llm(
        env,
        FakeLLM(
            script={
                "a6_interview": [
                    ToolCall(
                        "submit_turn",
                        turn("Welcome back! Still on film? Update a topic?", "research"),
                    ),
                ]
            }
        ),
    )
    first = ask(env, headers, "welcome_back")
    second = ask(env, headers, "welcome_back")
    assert first["text"] == second["text"] and first["fallback"] is False
    assert len(fake.calls) == 1
    assert all(v is None for v in first["proposed"].values())


def test_grounding_rules() -> None:
    said = "I like ML, philosophical questions and quantum stuff"
    assert iv.grounded("Machine learning", said)
    assert iv.grounded("Philosophy", said)
    assert iv.grounded("Quantum computing", said)
    assert not iv.grounded("Opera", said)
    assert not iv.grounded("AI", "I said nothing about it")
    assert iv.grounded("AI", "AI and society")


def test_the_rule_guide_revisits_a_topic_on_request(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile", json={"class_year": 2029, "interests": ["Physics"]}, headers=headers
    )
    t = ask(env, headers, "reply", "Can we talk about research?")
    assert t["topic"] == "research" and t["text"].startswith("Of course.")
    wrap = [{"role": "guide", "text": "Here's your portrait.", "topic": "wrapup"}]
    t = ask(env, headers, "reply", "Change something", wrap)
    assert t["topic"] == "wrapup" and "My interests" in t["quick_replies"]
    t = ask(env, headers, "reply", "My interests", wrap)
    assert t["topic"] == "interests"
    # An ordinary answer that mentions research is still an answer, not a request.
    talk = [{"role": "guide", "text": "What pulls at you?", "topic": "interests"}]
    t = ask(env, headers, "reply", "research on quantum stuff and film", talk)
    assert t["proposed"]["interests"] == ["Physics", "Research on quantum stuff", "Film"]
