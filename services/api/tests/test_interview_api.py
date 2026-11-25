"""The dashboard agent (`POST /agents/interview`, Issue #16) with FakeLLM and without a model:
the step-2 General Information questions in order, one per turn, quick replies from the
question file, answers mapped to their fields, retries, skips, the research-areas condition,
progress, the welcome-back greeting and its cache, and the checks on the model's turn."""

from __future__ import annotations

from typing import Any

import pytest
from agent_test_support import events, of, use_llm
from auth_test_support import Env
from llm_gateway.api import FakeLLM, ToolCall
from test_profile_support import db_url_fixture, env_fixture, login  # noqa: F401

pytestmark = pytest.mark.db

PLAN_CHIPS = ["Work in industry", "Graduate school", "Medical or law school", "Undecided", "Skip"]
PACE_CHIPS = ["Early", "On time", "Flexible", "Skip"]
EMPTY_FACTS: dict[str, Any] = {
    "post_grad_plan": None,
    "pace": None,
    "wants_research": None,
    "research_areas": [],
    "courses_per_term": None,
    "terms_away": None,
    "class_formats": None,
    "theory_vs_application": None,
}


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


def sent(turn: dict[str, Any]) -> dict[str, Any]:
    """The fields the turn proposes."""
    return {k: v for k, v in turn["proposed"].items() if v is not None}


def keep(env: Env, headers: dict[str, str], turn: dict[str, Any]) -> None:
    """The browser keeps the proposed answer."""
    if proposed := sent(turn):
        resp = env.client.patch("/me/profile", json=proposed, headers=headers)
        assert resp.status_code == 200, resp.text


class Talk:
    """A conversation as the browser keeps it."""

    def __init__(self, env: Env, headers: dict[str, str], *, kept: bool = False) -> None:
        self.env, self.headers, self.kept = env, headers, kept
        self.history: list[dict[str, Any]] = []

    def _guide(self, turn: dict[str, Any]) -> None:
        self.history.append({"role": "guide", "text": turn["text"], "topic": turn["topic"]})

    def start(self) -> dict[str, Any]:
        turn = ask(self.env, self.headers, "start")
        self._guide(turn)
        return turn

    def say(self, text: str) -> dict[str, Any]:
        turn = ask(self.env, self.headers, "reply", text, self.history)
        if self.kept:
            keep(self.env, self.headers, turn)
        self.history.append({"role": "student", "text": text})
        self._guide(turn)
        return turn


def guide(topic: str, text: str = "A question?") -> list[dict[str, Any]]:
    return [{"role": "guide", "text": text, "topic": topic}]


# ------------------------------------------------------------------------------ no model


@pytest.mark.parametrize("kept", [False, True])
def test_the_rule_guide_asks_every_question_in_order(env: Env, kept: bool) -> None:
    # Unkept answers still count as covered in the conversation; kept ones in the record.
    headers = login(env)
    talk = Talk(env, headers, kept=kept)
    t = talk.start()
    assert t["topic"] == "post_grad_plan" and t["fallback"] is True
    assert t["quick_replies"] == PLAN_CHIPS and t["progress"] == 0
    assert "What do you plan to do after you graduate?" in t["text"]
    assert t["answered"] is None and sent(t) == {}

    t = talk.say("Graduate school")
    assert sent(t) == {"post_grad_plan": "grad_school"} and t["answered"] == "post_grad_plan"
    assert t["topic"] == "pace" and t["quick_replies"] == PACE_CHIPS
    assert t["progress"] == pytest.approx(round(1 / 7, 3))
    assert t["text"].startswith("Graduate school: noted.")

    t = talk.say("early")
    assert sent(t) == {"pace": "early"} and t["topic"] == "wants_research"
    assert t["quick_replies"] == ["Yes", "No", "Skip"]

    t = talk.say("Yes")
    assert sent(t) == {"wants_research": True} and t["topic"] == "research_areas"
    assert t["quick_replies"] == ["Skip"]
    assert t["progress"] == pytest.approx(round(3 / 8, 3))  # research areas now apply

    t = talk.say("machine learning theory, condensed matter")
    assert sent(t) == {"research_areas": ["Machine learning theory", "Condensed matter"]}
    assert t["topic"] == "courses_per_term"
    assert t["quick_replies"] == ["3 courses", "4 courses", "5 courses", "Skip"]

    t = talk.say("four")
    assert sent(t) == {"courses_per_term": 4} and t["topic"] == "terms_away"
    assert t["quick_replies"] == ["None", "Skip"]

    t = talk.say("autumn 2027 abroad")
    assert sent(t) == {"terms_away": [{"term": "2027-AU", "kind": "abroad"}]}
    assert t["topic"] == "class_formats"
    assert t["quick_replies"] == ["Seminar", "Lecture", "Lab", "Online", "Skip"]

    t = talk.say("seminars and labs")
    assert sent(t) == {"class_formats": ["seminar", "lab"]}
    assert t["topic"] == "theory_vs_application"
    assert t["quick_replies"] == [*(str(n) for n in range(1, 11)), "Skip"]

    t = talk.say("7")
    assert sent(t) == {"theory_vs_application": 7} and t["answered"] == "theory_vs_application"
    assert t["topic"] == "wrapup" and t["done"] is True and t["progress"] == 1
    assert t["quick_replies"] == []
    assert "portrait" not in t["proposed"]


def test_no_to_research_skips_the_research_areas(env: Env) -> None:
    headers = login(env)
    t = ask(env, headers, "reply", "No", guide("wants_research"))
    assert sent(t) == {"wants_research": False} and t["topic"] == "post_grad_plan"
    history = [
        *guide("wants_research"),
        {"role": "student", "text": "no"},
        *guide("post_grad_plan"),
        {"role": "student", "text": "Undecided"},
        *guide("pace"),
    ]
    t = ask(env, headers, "reply", "Flexible", history)
    assert t["topic"] == "courses_per_term"  # research_areas never asked
    assert t["progress"] == pytest.approx(round(3 / 7, 3))


def test_an_unclear_answer_is_asked_again_and_skip_moves_on(env: Env) -> None:
    headers = login(env)
    talk = Talk(env, headers)
    talk.start()
    t = talk.say("pizza")
    assert t["retry"] is True and t["topic"] == "post_grad_plan"
    assert t["answered"] is None and sent(t) == {} and t["progress"] == 0
    assert t["quick_replies"] == PLAN_CHIPS and "didn't catch" in t["text"]
    t = talk.say("Skip")
    assert t["retry"] is False and t["answered"] is None and sent(t) == {}
    assert t["topic"] == "pace" and t["progress"] == pytest.approx(round(1 / 7, 3))
    # A retry in the history does not count as covered; the skip does.
    t = talk.say("on time")
    assert t["topic"] == "wants_research"


def test_integers_must_be_in_range(env: Env) -> None:
    headers = login(env)
    t = ask(env, headers, "reply", "7", guide("courses_per_term"))
    assert t["retry"] is True and t["topic"] == "courses_per_term" and sent(t) == {}
    assert "from 1 to 6" in t["text"]
    t = ask(env, headers, "reply", "11", guide("theory_vs_application"))
    assert t["retry"] is True and "Theory" in t["text"]


def test_start_resumes_after_the_record_and_the_memory(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile",
        json={"post_grad_plan": "industry", "interview": {"covered": ["pace"]}},
        headers=headers,
    )
    t = ask(env, headers, "start")
    assert t["topic"] == "wants_research" and t["text"].startswith("Welcome back.")
    assert t["progress"] == pytest.approx(round(2 / 7, 3))


def test_research_areas_follow_a_yes_in_the_record_and_merge(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile",
        json={"post_grad_plan": "industry", "pace": "early", "wants_research": True},
        headers=headers,
    )
    t = ask(env, headers, "start")
    assert t["topic"] == "research_areas" and t["quick_replies"] == ["Skip"]
    assert "for example machine learning theory" in t["text"]  # the help line
    t = ask(env, headers, "reply", "quantum materials and AI", guide("research_areas"))
    assert sent(t) == {"research_areas": ["Quantum materials", "AI"]}


def test_welcome_back_without_a_model_recalls_and_resumes(env: Env) -> None:
    headers = login(env, "quiet-heron")
    env.client.patch("/me/profile", json={"post_grad_plan": "grad_school"}, headers=headers)
    t = ask(env, headers, "welcome_back")
    assert t["text"].startswith("Welcome back, quiet-heron.")
    assert "Graduate school" in t["text"] and t["topic"] == "pace"
    assert t["quick_replies"] == PACE_CHIPS and sent(t) == {}


def test_reply_after_the_wrapup_stays_done(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile",
        json={
            "post_grad_plan": "industry",
            "pace": "early",
            "wants_research": False,
            "courses_per_term": 4,
            "terms_away": [],
            "class_formats": [],
            "theory_vs_application": 5,
        },
        headers=headers,
    )
    t = ask(env, headers, "reply", "thanks!", guide("wrapup"))
    assert t["topic"] == "wrapup" and t["done"] is True and t["progress"] == 1


# ------------------------------------------------------------------------------ with a model


def turn(text: str, topic: str, skipped: bool = False, **facts: Any) -> dict[str, Any]:
    return {"text": text, "topic": topic, "skipped": skipped, "facts": {**EMPTY_FACTS, **facts}}


def script(*payloads: dict[str, Any]) -> FakeLLM:
    return FakeLLM(script={"a6_interview": [ToolCall("submit_turn", p) for p in payloads]})


def test_the_model_writes_the_question_and_the_server_reads_the_answer(env: Env) -> None:
    headers = login(env)
    fake = use_llm(
        env,
        script(
            turn(
                "Graduate school, great. Since you're aiming there, how fast do you want to "
                "graduate?",
                "pace",
                post_grad_plan="industry",  # the rules read the button: ignored
            )
        ),
    )
    t = ask(env, headers, "reply", "Graduate school", guide("post_grad_plan"))
    assert t["fallback"] is False and t["topic"] == "pace"
    assert sent(t) == {"post_grad_plan": "grad_school"} and t["answered"] == "post_grad_plan"
    assert t["quick_replies"] == PACE_CHIPS  # set by the server
    first = fake.calls[0]["messages"][0]["content"]
    assert '<untrusted_source id="answer">' in first and "Graduate school" in first
    assert '<untrusted_source id="student_md">' in first and "# Student record" in first
    # The model never sees the email or the username.
    assert "quiet-heron" not in first and "uchicago.edu" not in first


def test_the_model_maps_a_typed_answer_the_rules_cannot_read(env: Env) -> None:
    headers = login(env)
    use_llm(
        env,
        script(turn("A lab of your own one day! How fast?", "pace", post_grad_plan="grad_school")),
    )
    t = ask(env, headers, "reply", "I hope to run my own lab one day", guide("post_grad_plan"))
    assert t["fallback"] is False and t["retry"] is False
    assert sent(t) == {"post_grad_plan": "grad_school"} and t["answered"] == "post_grad_plan"


def test_the_model_reads_a_skip(env: Env) -> None:
    headers = login(env)
    use_llm(env, script(turn("No problem. How fast?", "pace", skipped=True)))
    t = ask(env, headers, "reply", "I'd prefer to keep that private", guide("post_grad_plan"))
    assert t["topic"] == "pace" and sent(t) == {} and t["retry"] is False
    assert t["progress"] == pytest.approx(round(1 / 7, 3))


def test_an_unsupported_answer_gets_a_repair_then_a_retry(env: Env) -> None:
    headers = login(env)
    fake = use_llm(
        env,
        script(
            # 4 is in range, but the student wrote no number: not grounded.
            turn("Four it is. Any quarters away?", "terms_away", courses_per_term=4),
            turn("Sorry, how many courses each quarter, as a number?", "courses_per_term"),
        ),
    )
    t = ask(env, headers, "reply", "a normal load", guide("courses_per_term"))
    assert len(fake.calls) == 2
    assert t["fallback"] is False and t["retry"] is True and t["topic"] == "courses_per_term"
    assert sent(t) == {} and t["quick_replies"] == ["3 courses", "4 courses", "5 courses", "Skip"]


def test_a_wrong_topic_twice_falls_back_to_the_rules(env: Env) -> None:
    headers = login(env)
    use_llm(
        env,
        script(
            turn("Which formats do you like?", "class_formats"),
            turn("Which formats, then?", "class_formats"),
        ),
    )
    # An unreadable answer must be asked again; the model moves on twice, so the rules ask.
    t = ask(env, headers, "reply", "pizza", guide("post_grad_plan"))
    assert t["fallback"] is True and t["retry"] is True and t["topic"] == "post_grad_plan"


def test_the_model_may_pick_the_order_but_not_a_covered_question(env: Env) -> None:
    headers = login(env)
    use_llm(env, script(turn("Seminars, lectures, labs or online?", "class_formats")))
    t = ask(env, headers, "start")
    assert t["fallback"] is False and t["topic"] == "class_formats"
    env.client.patch("/me/profile", json={"class_formats": ["lab"]}, headers=headers)
    use_llm(
        env,
        script(
            turn("Formats again?", "class_formats"),
            turn("Formats again?", "class_formats"),
        ),
    )
    t = ask(env, headers, "start")
    assert t["fallback"] is True and t["topic"] == "post_grad_plan"


def test_research_areas_open_after_a_yes_in_this_conversation(env: Env) -> None:
    headers = login(env)
    use_llm(env, script(turn("Which areas interest you?", "research_areas")))
    t = ask(env, headers, "reply", "yes!", guide("wants_research"))
    assert t["topic"] == "research_areas" and sent(t) == {"wants_research": True}
    assert t["quick_replies"] == ["Skip"]


def test_the_model_cannot_ask_research_areas_after_a_no(env: Env) -> None:
    headers = login(env)
    use_llm(
        env,
        script(
            turn("Which areas?", "research_areas"),
            turn("Which areas?", "research_areas"),
        ),
    )
    t = ask(env, headers, "reply", "nope", guide("wants_research"))
    assert t["fallback"] is True and t["topic"] == "post_grad_plan"
    assert sent(t) == {"wants_research": False}


def test_a_named_course_gets_one_repair_then_the_rules_take_over(env: Env) -> None:
    headers = login(env)
    use_llm(
        env,
        script(
            turn("Try PHYS 13100! What after college?", "post_grad_plan"),
            turn("PHYS 13100 again. What after college?", "post_grad_plan"),
        ),
    )
    t = ask(env, headers, "start")
    assert t["fallback"] is True and "PHYS" not in t["text"] and t["courses"] == []


def test_the_wrapup_with_a_model(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile",
        json={
            "post_grad_plan": "industry",
            "pace": "early",
            "wants_research": False,
            "courses_per_term": 4,
            "terms_away": [],
            "class_formats": ["lab"],
        },
        headers=headers,
    )
    use_llm(env, script(turn("Thank you! You can change any answer on your dashboard.", "wrapup")))
    t = ask(env, headers, "reply", "8", guide("theory_vs_application"))
    assert sent(t) == {"theory_vs_application": 8} and t["done"] is True
    assert t["progress"] == 1 and t["topic"] == "wrapup" and t["quick_replies"] == []


def test_welcome_back_is_cached_per_record(env: Env) -> None:
    headers = login(env)
    env.client.patch("/me/profile", json={"post_grad_plan": "grad_school"}, headers=headers)
    fake = use_llm(
        env,
        script(
            turn("Welcome back! Still set on graduate school? How fast do you want to go?", "pace")
        ),
    )
    first = ask(env, headers, "welcome_back")
    second = ask(env, headers, "welcome_back")
    assert first["text"] == second["text"] and first["fallback"] is False
    assert first["quick_replies"] == PACE_CHIPS and sent(first) == {}
    assert len(fake.calls) == 1
    # One key per account (so deleting the account deletes it): a changed record misses it.
    assert len(env.redis.keys("me:welcome:*")) == 1
    env.client.patch("/me/profile", json={"post_grad_plan": "industry"}, headers=headers)
    third = ask(env, headers, "welcome_back")
    assert len(fake.calls) == 2 and third["fallback"] is True
    assert len(env.redis.keys("me:welcome:*")) == 1
