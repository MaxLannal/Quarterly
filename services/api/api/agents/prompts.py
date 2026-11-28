"""Versioned agent prompts (`prompts/*.md`, SPEC "Versioned prompts").

Each file starts with a front-matter block naming its `id` and integer `version`; the version
string logged with every `llm_call` is `<id>@<version>`. A version bump must pass that agent's
eval set (`make evals`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    task: str
    text: str

    @property
    def version_tag(self) -> str:
        return f"{self.id}@{self.version}"


def prompts_dir() -> Path:
    """`PROMPTS_DIR` if set, else the nearest `prompts/` folder above this file or the
    working directory (the repository root; `/app/prompts` in the API image)."""
    explicit = os.environ.get("PROMPTS_DIR")
    if explicit:
        return Path(explicit)
    for base in (Path(__file__).resolve(), Path.cwd()):
        for folder in (base, *base.parents):
            candidate = folder / "prompts"
            if (candidate / "a1_planner.md").is_file():
                return candidate
    raise FileNotFoundError("prompts/ not found (set PROMPTS_DIR)")


def parse_prompt(raw: str, name: str) -> Prompt:
    if not raw.startswith("---\n"):
        raise ValueError(f"{name}: missing the version header")
    head, _, body = raw[4:].partition("\n---\n")
    meta = yaml.safe_load(head) or {}
    if meta.get("id") != name or not isinstance(meta.get("version"), int):
        raise ValueError(f"{name}: the header needs `id: {name}` and an integer `version`")
    return Prompt(
        id=name, version=meta["version"], task=str(meta.get("task", "")), text=body.strip()
    )


@lru_cache
def load_prompt(name: str) -> Prompt:
    path = prompts_dir() / f"{name}.md"
    return parse_prompt(path.read_text(encoding="utf-8"), name)
