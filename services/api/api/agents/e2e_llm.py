"""A FakeLLM for end-to-end tests of the real stack (prompt 12, journeys A-D): `LLM_FAKE=e2e`.

It never calls a provider. Each request gets an answer built from the request itself, so every
agent runs through the real loop (tools, validation, citations checked against tool results):

- A1 preferences: for each requirement listed, the first candidates it needs.
- A1 rationale: one short note per quarter of every variant, citing a course in it.
- A2 advisor: looks up the first course code the student names, drafts adding it to the
  plan's last listed quarter, then answers citing that course.
- Scope gate, moderation, forum extraction, summaries and cold-start estimates: fixed safe
  answers.

Allowed only with ENVIRONMENT=development or test (`Settings.production_problems`).
"""

from __future__ import annotations

import re
from typing import Any

from llm_gateway.api import FakeLLM, ToolCall

CODE = re.compile(r"\b[A-Z]{2,5} \d{5}\b")
TERM = re.compile(r"\b(\d{4})-(AU|WI|SP)\b")
NODE_LINE = re.compile(r"^- (\S+) \(.*?\): needs (\d+) more; \d+ candidates: (.*)$")
QUARTER_LINE = re.compile(r"^- (\d{4}-(?:AU|WI|SP|SU)) \([^)]*\): (.*)$")
POST_ID = re.compile(r'<untrusted_source id="(?:post-)?(\d+)"')


def _text(messages: list[Any]) -> str:
    """Every piece of text in the conversation, in order."""
    parts: list[str] = []
    for message in messages:
        content = message.content if hasattr(message, "content") else message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    for key in ("text", "content"):
                        value = block.get(key)
                        if isinstance(value, str):
                            parts.append(value)
    return "\n".join(parts)


def _tool_results(messages: list[Any]) -> int:
    n = 0
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            n += sum(1 for b in content if isinstance(b, dict) and b.get("type") == "tool_result")
    return n


def _student_message(messages: list[Any]) -> str:
    first = messages[0] if messages else None
    if first is None:
        return ""
    content = first.content if hasattr(first, "content") else first.get("content")
    return content if isinstance(content, str) else _text([first])


def _preferences(text: str) -> ToolCall:
    nodes = []
    for line in text.splitlines():
        m = NODE_LINE.match(line.strip())
        if m:
            node_id, need, rest = m.group(1), int(m.group(2)), m.group(3)
            codes = list(dict.fromkeys(CODE.findall(rest)))[: max(1, need)]
            picks = [{"code": c, "score": 80, "reason": "Fits the stated goals."} for c in codes]
            nodes.append({"node_id": node_id, "picks": picks})
    return ToolCall("submit_preferences", {"nodes": nodes[:20]})


def _rationale(text: str) -> ToolCall:
    variants: list[dict[str, Any]] = []
    for line in text.splitlines():
        head = re.match(r"^(Option [A-C])\b", line.strip())
        if head:
            variants.append({"label": head.group(1), "quarters": []})
            continue
        m = QUARTER_LINE.match(line.strip())
        if m and variants:
            codes = list(dict.fromkeys(CODE.findall(m.group(2))))
            note = "Keeps the load even and moves the programs forward."
            variants[-1]["quarters"].append(
                {"term": m.group(1), "courses": codes, "text": note,
                 "citations": [f"course:{codes[0]}"] if codes else []}
            )  # fmt: skip
    return ToolCall("submit_rationale", {"variants": variants})


def _advisor(messages: list[Any]) -> Any:
    question = _student_message(messages)
    codes = CODE.findall(question)
    done = _tool_results(messages)
    code = codes[0] if codes else None
    if code is None:
        return ToolCall(
            "submit_answer",
            {"text": "Ask me about a course by its code, for example CMSC 14100.", "citations": []},
        )
    if done == 0:
        return [ToolCall("get_plan", {}), ToolCall("get_course", {"code": code})]
    if done <= 2:
        terms = sorted(
            {f"{y}-{q}" for y, q in TERM.findall(_text(messages))},
            key=lambda t: (int(t[:4]), {"WI": 0, "SP": 1, "AU": 3}[t[5:]]),
        )
        term = terms[-1] if terms else "2028-AU"
        op = {"op": "add", "course": code, "term": term, "from_term": None, "to_term": None}
        return ToolCall("propose_change_set", {"ops": [op]})
    text = (
        f"{code} is a good fit for that goal. I drafted a change that adds it to your plan; "
        "check the card and apply it if you agree."
    )
    return ToolCall(
        "submit_answer",
        {"text": text, "citations": [{"kind": "course", "id": code, "label": code}]},
    )


def _answer(call: dict[str, Any]) -> Any:
    task, messages = call["task"], call.get("messages") or []
    text = _text(messages)
    tools = set(call.get("tools") or [])
    if task.startswith("a1_"):
        if "submit_rationale" in tools:
            return _rationale(text)
        return _preferences(text)
    if task in ("a2_advisor_chat", "a2_advisor_escalation"):
        return _advisor(messages)
    if task == "a2_scope_classifier":
        return {"label": "suspicious" if "system prompt" in text.lower() else "in_scope"}
    if task == "a4_moderation":
        return {"label": "ok"}
    if task == "a3_forum_extraction":
        return {
            "workload_mentions": [],
            "difficulty_cues": [],
            "exam_style": [],
            "prerequisite_advice": [],
        }
    if task == "a3_forum_summary":
        ids = [int(i) for i in POST_ID.findall(text)][:2] or [0]
        marks = " ".join(f"[{n + 1}]" for n in range(len(ids)))
        return {
            "text": f"Students describe steady weekly work and fair exams {marks}.",
            "citations": ids,
        }
    if task == "a3_cold_start_estimate":
        return {"workload_hours": 8, "difficulty": 3, "reason": "Estimated from the course level."}
    raise ValueError(f"e2e LLM has no answer for task {task}")


def e2e_llm() -> FakeLLM:
    """A FakeLLM whose every answer is computed from the request (see the module docstring)."""
    fake = FakeLLM(script={})

    def on_call(call: dict[str, Any]) -> None:
        fake.script.setdefault(call["task"], []).append(_answer(call))
        fake.calls.clear()  # keep memory flat in a long-running server

    fake.on_call = on_call
    return fake
