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
    import api.agents.chat as chat
    import api.agents.generate as generate
    from api.agents.tools import TOOLS

    schemas: dict[str, Any] = {name: make(MagicMock()).input_schema for name, make in TOOLS.items()}
    for module in (generate, chat):
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

    pairs = json.loads((Path(__file__).parent / "fixtures" / "live" / "p3-off-homework.json").read_text())
    truncated = [p for p in pairs if p["response"]["stop_reason"] == "max_tokens"]
    assert truncated and all(p["response"]["tool_calls"][0]["input"] == {} for p in truncated)
    used = max(p["response"]["usage"]["output_tokens"] for p in truncated)
    assert load_routing().route("a2_scope_classifier").max_tokens >= 4 * used
