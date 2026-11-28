"""Bugs found by the live agent tests (prompt 13). No API calls."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock


def _enum_on_type_list(node: Any, path: str = "$") -> list[str]:
    """Paths where a schema puts `enum` next to a list of types, which the API rejects."""
    found: list[str] = []
    if isinstance(node, dict):
        if "enum" in node and isinstance(node.get("type"), list):
            found.append(path)
        for key, value in node.items():
            found += _enum_on_type_list(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += _enum_on_type_list(value, f"{path}[{i}]")
    return found


def test_no_agent_tool_schema_puts_an_enum_on_a_list_of_types() -> None:
    """Live finding (phase 2): every advisor turn failed with HTTP 400 "tools.2.custom:
    Invalid schema: Enum value 'AU' does not match declared type ['string', 'null']" (the
    `quarter` filter of search_courses). FakeLLM never sees tool schemas, so only a live call
    showed it."""
    import api.agents.planner.chat as chat
    import api.agents.planner.state as state
    from api.agents.tools import TOOLS
    from llm_gateway.loop import submit_schema
    from llm_gateway.types import SubmitTool

    schemas: dict[str, Any] = {name: make(MagicMock()).input_schema for name, make in TOOLS.items()}
    for model in (
        state.QuestionsSubmission,
        state.PlanSubmission,
        state.RepairSubmission,
        state.ExplanationsSubmission,
    ):
        schemas[model.__name__] = submit_schema(SubmitTool("x", "x", model))
    for module in (chat,):
        for attr in dir(module):
            value = getattr(module, attr)
            if attr.endswith("_SCHEMA") and isinstance(value, dict):
                schemas[f"{module.__name__}.{attr}"] = value
    assert len(schemas) >= 8
    bad = {name: paths for name, schema in schemas.items() if (paths := _enum_on_type_list(schema))}
    assert bad == {}


def test_the_scope_classifier_has_room_for_its_answer() -> None:
    """Live finding (phase 3): at max_tokens 50, Haiku 5.5 stopped mid-answer (stop_reason
    max_tokens, an empty `submit`) on 5 of 6 off-topic messages. The chat then took its
    in_scope fallback and paid for the Sonnet advisor instead of the fixed refusal. The
    recording is the real answer; the limit must leave ample room above what it used."""
    import json
    from pathlib import Path

    from llm_gateway.routing import load_routing

    pairs = json.loads(
        (Path(__file__).parent / "fixtures" / "live" / "p3-off-homework.json").read_text()
    )
    truncated = [p for p in pairs if p["response"]["stop_reason"] == "max_tokens"]
    assert truncated and all(p["response"]["tool_calls"][0]["input"] == {} for p in truncated)
    used = max(p["response"]["usage"]["output_tokens"] for p in truncated)
    assert load_routing().route("a2_scope_classifier").max_tokens >= 4 * used


def test_planner_output_limits_leave_room_for_thinking_and_a_whole_plan() -> None:
    """Live finding (phase 1, the old A1): per-step limits of 1500 and 1200 cut every answer
    off on Opus 5.5, whose thinking cannot be turned off. The recordings are the real answers;
    the planner's generation route writes a whole plan in one call, so its cap must leave at
    least 2.5 times the largest cut-off answer, and the chat route at least that much for one
    answer with three proposals."""
    import json
    from pathlib import Path

    from llm_gateway.routing import load_routing

    used = 0
    for name in ("a1-p1-undecided-sonnet.json", "a1-p2-cs-math-bxms-opus.json"):
        for pair in json.loads((Path(__file__).parent / "fixtures" / "live" / name).read_text()):
            r = pair["response"]
            if r["stop_reason"] == "max_tokens":
                used = max(used, r["usage"]["output_tokens"])
    assert used
    routing = load_routing()
    assert routing.route("a1_planner_agent").max_tokens >= 2.5 * used
    assert routing.route("a1_planner_chat").max_tokens >= 2.5 * used


def test_the_test_run_cannot_reach_a_real_model() -> None:
    """`.env` now turns the app's AI on (LLM_LIVE=true, real keys); tests must not inherit it."""
    from api.config import Settings

    settings = Settings()  # reads .env, but the root conftest's environment wins
    assert settings.llm_live is False
    assert settings.anthropic_api_key.get_secret_value() == ""
    assert settings.openrouter_api_key.get_secret_value() == ""
