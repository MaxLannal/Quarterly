"""data/planner/plan-guideline.md (the planning rules) and data/planner/config.yaml (the limits).

The whole guideline goes into the planner agent's system prompt; the parsed rules let the code
check `guideline:Gnn` citations and show a rule's text on its chip.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict

PLANNER_DIR = Path(__file__).resolve().parents[5] / "data" / "planner"
GUIDELINE_FILE = PLANNER_DIR / "plan-guideline.md"
CONFIG_FILE = PLANNER_DIR / "config.yaml"

Tier = Literal["hard", "strong", "preference", "tiebreak"]
TIERS: tuple[Tier, ...] = ("hard", "strong", "preference", "tiebreak")

_RULE = re.compile(r"^- \*\*(G\d+)\*\* · (\w+) · (.+)$")
_WHY = re.compile(r"^\s+Why: (.+)$")
_SOURCE = re.compile(r"^\s+Source: (\S+)")


@dataclass(frozen=True)
class Rule:
    id: str
    tier: Tier
    text: str
    why: str
    source: str | None = None


@dataclass(frozen=True)
class Guideline:
    #: The whole file, for the system prompt.
    text: str
    rules: dict[str, Rule]
    #: Section heading -> the rule ids in it, in file order.
    sections: dict[str, list[str]] = field(default_factory=dict)


def parse_guideline(text: str) -> Guideline:
    """Parse the rule lines; raise `ValueError` naming the rule on a duplicate id, an unknown
    tier or a missing `Why:` line."""
    rules: dict[str, Rule] = {}
    sections: dict[str, list[str]] = {}
    section = ""
    pending: dict[str, str] | None = None

    def close() -> None:
        nonlocal pending
        if pending is None:
            return
        if not pending.get("why"):
            raise ValueError(f"{pending['id']} has no Why line")
        rules[pending["id"]] = Rule(
            id=pending["id"],
            tier=cast(Tier, pending["tier"]),
            text=pending["text"],
            why=pending["why"],
            source=pending.get("source"),
        )
        sections.setdefault(section, []).append(pending["id"])
        pending = None

    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced  # the format example at the top is not a rule
            continue
        if fenced:
            continue
        if line.startswith("## "):
            close()
            section = line[3:].strip()
            continue
        if m := _RULE.match(line):
            close()
            rid, tier, body = m.groups()
            if rid in rules:
                raise ValueError(f"{rid} appears twice")
            if tier not in TIERS:
                raise ValueError(f"{rid} has an unknown tier {tier!r}")
            pending = {"id": rid, "tier": tier, "text": body.strip()}
            continue
        if pending is not None:
            if m := _WHY.match(line):
                pending["why"] = m.group(1).strip()
            elif m := _SOURCE.match(line):
                pending["source"] = m.group(1).strip()
            elif not line.strip() or not line.startswith(" "):
                close()
    close()
    return Guideline(text=text, rules=rules, sections=sections)


@lru_cache(maxsize=1)
def load_guideline(path: Path = GUIDELINE_FILE) -> Guideline:
    return parse_guideline(path.read_text(encoding="utf-8"))


class PlannerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    questions_max: int = 2
    min_options: int = 2
    max_options: int = 5
    repair_rounds: int = 5
    thrash_same_errors: int = 3
    max_ops_per_round: int = 12
    fix_warning_codes: list[str] = ["V04", "V10", "V11"]
    max_polish_rounds: int = 2
    tool_calls_per_step: int = 6
    chat_proposals_max: int = 3
    working_info_chars: int = 4000
    run_seconds: int = 300
    write_seconds: int = 600
    state_ttl_days: int = 1


@lru_cache(maxsize=1)
def load_planner_config(path: Path = CONFIG_FILE) -> PlannerConfig:
    return PlannerConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
