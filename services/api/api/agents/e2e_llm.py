"""A FakeLLM for end-to-end tests of the real stack (prompt 12, journeys A-D): `LLM_FAKE=e2e`.

It never calls a provider. Each request gets an answer built from the request itself, so every
agent runs through the real loop (tools, validation, citations checked against tool results):

- Planner agent (generate): no questions; a plan built from the requirements brief (each
  unmet requirement takes its first candidates in later quarters where they are offered; it
  may not verify, and the repair rounds change nothing); one reason per group that names the
  student's first interest.
- Planner chat: looks up the first course code the student names and proposes adding it to
  the plan's last listed quarter; "I hate <code>" records an avoid preference instead.
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


BRIEF_LINE = re.compile(r"^- (\S+) \((.*?)\): need (\d+)")
CANDIDATE = re.compile(r"([A-Z]{2,5} \d{5}) \[([^\]]*)\]")
PROGRAM = re.compile(r"^## (\S+?):")
INTERESTS = re.compile(r"^- Interests: (.+)$", re.MULTILINE)
QUARTER_ORDER = {"WI": 0, "SP": 1, "SU": 2, "AU": 3}


def _term_key(term: str) -> tuple[int, int]:
    return int(term[:4]), QUARTER_ORDER[term[5:]]


def _planner_fill(text: str) -> ToolCall:
    """A plan built from the requirements brief: each unmet requirement takes its first
    candidates, in strictly later quarters (so a sequence stays in order), in a quarter the
    candidate is usually offered, at most four courses a quarter."""
    head = text.split("# Quarters to plan", 1)[-1].split("#", 1)[0]
    terms = sorted(set(re.findall(r"\d{4}-(?:AU|WI|SP)", head)), key=_term_key)
    load: dict[str, int] = {t: 0 for t in terms}
    used: set[str] = set()
    groups: list[dict[str, Any]] = []
    program = ""
    lines = text.splitlines()
    for n, line in enumerate(lines):
        if m := PROGRAM.match(line.strip()):
            program = m.group(1)
            continue
        m = BRIEF_LINE.match(line.strip())
        if not m or n + 1 >= len(lines) or "candidates:" not in lines[n + 1]:
            continue
        label, need = m.group(2), int(m.group(3))
        placed: list[dict[str, str]] = []
        after = -1
        for code, offered in CANDIDATE.findall(lines[n + 1]):
            if len(placed) >= need or code in used:
                continue
            quarters = (
                set(offered.split("/"))
                if "/" in offered or offered in QUARTER_ORDER
                else {"AU", "WI", "SP"}
            )
            slot = next(
                (i for i, t in enumerate(terms) if i > after and t[5:] in quarters and load[t] < 4),
                None,
            )
            if slot is None:
                continue
            term = terms[slot]
            load[term] += 1
            used.add(code)
            after = slot
            placed.append({"code": code, "term": term})
        if placed:
            groups.append(
                {
                    "id": f"g{len(groups) + 1}",
                    "title": label[:80] or "Requirement",
                    "kind": "core" if program == "core" else "major",
                    "courses": placed,
                    "why": "This meets a requirement early, in the quarters it is usually offered.",
                    "rules": ["G01", "G08"],
                }
            )
    return ToolCall("submit_plan", {"groups": groups[:24] or [], "notes": ""})


def _planner_explain(text: str) -> ToolCall:
    interests = INTERESTS.search(text)
    topic = interests.group(1).split(";")[0].strip() if interests else "your goals"
    ids = list(dict.fromkeys(re.findall(r"\((g\d+)\)", text)))
    return ToolCall(
        "submit_explanations",
        {
            "groups": [
                {
                    "id": gid,
                    "why": f"You said you are interested in {topic}. This group builds toward it.",
                    "citations": ["profile:interests"] if interests else [],
                }
                for gid in ids
            ]
        },
    )


def _planner(tools: set[str], text: str) -> Any:
    if "submit_questions" in tools:
        return ToolCall("submit_questions", {"questions": []})
    if "submit_plan" in tools:
        return _planner_fill(text)
    if "submit_repair" in tools:
        return ToolCall("submit_repair", {"summary": "No change.", "ops": [], "bent": []})
    return _planner_explain(text)


def _planner_chat(messages: list[Any]) -> Any:
    """Names a course code: drafts adding it to the plan's last quarter. Says it hates a
    course: notes the preference first."""
    text = _text(messages)
    question = text.rsplit("# Message", 1)[-1]
    codes = CODE.findall(question)
    done = _tool_results(messages)
    code = codes[0] if codes else None
    if code is None:
        return ToolCall(
            "submit_answer",
            {"text": "Ask me about a course by its code, for example CMSC 14100.", "citations": []},
        )
    hate = "hate" in question.lower() or "don't want" in question.lower()
    if done == 0 and hate:
        return ToolCall(
            "note_preference", {"text": question.strip()[:200], "kind": "avoid", "courses": [code]}
        )
    if hate:
        return ToolCall(
            "submit_answer",
            {"text": f"Noted: I will not propose {code} again.", "citations": []},
        )
    if done == 0:
        return [ToolCall("get_plan", {}), ToolCall("get_course", {"code": code})]
    if done <= 2:
        terms = sorted({f"{y}-{q}" for y, q in TERM.findall(text)}, key=_term_key)
        term = terms[-1] if terms else "2028-AU"
        op = {"op": "add", "course": code, "term": term, "from_term": None, "to_term": None}
        return ToolCall(
            "propose_change_set",
            {
                "ops": [op],
                "title": f"Add {code}",
                "kind": "elective",
                "why": f"{code} fits what you asked for.",
                "rules": ["G22"],
            },
        )
    text = f"{code} is a good fit for that goal. I proposed adding it; accept it beside the plan."
    return ToolCall(
        "submit_answer",
        {"text": text, "citations": [{"kind": "course", "id": code, "label": code}]},
    )


def _answer(call: dict[str, Any]) -> Any:
    task, messages = call["task"], call.get("messages") or []
    text = _text(messages)
    tools = set(call.get("tools") or [])
    if task == "a1_planner_agent":  # the requirements brief is in the system prompt
        return _planner(tools, f"{call.get('system') or ''}\n{text}")
    if task == "a1_planner_chat":
        return _planner_chat(messages)
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
