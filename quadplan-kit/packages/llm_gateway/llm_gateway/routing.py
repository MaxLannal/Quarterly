"""`llm_routing.yaml`: the only place model ids live (CLAUDE.md hard rule).

Each task names a primary (Anthropic) model, its effort and output cap, and an OpenRouter
fallback model. `prices` gives list prices per million tokens, used for `llm_call.cost_usd`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from llm_gateway.types import Usage

ROUTING_FILE = "llm_routing.yaml"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Providers(_Model):
    primary: Literal["anthropic"] = "anthropic"
    fallback: Literal["openrouter"] | None = "openrouter"
    fallback_after_errors: int = Field(default=2, ge=1)


class FallbackRoute(_Model):
    provider: Literal["openrouter"]
    model: str


class TaskRoute(_Model):
    model: str
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    max_tokens: int = Field(ge=1)
    fallback: FallbackRoute | None = None
    #: Ask the API to re-run a declined request on another model (server-side fallback,
    #: "default" routing; Opus and Sonnet only).
    refusal_fallback: bool = False


class Price(_Model):
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float
    cache_write: float

    def cost(self, usage: Usage) -> float:
        return (
            usage.input_tokens * self.input
            + usage.output_tokens * self.output
            + usage.cache_read_tokens * self.cache_read
            + usage.cache_write_tokens * self.cache_write
        ) / 1_000_000


class Routing(_Model):
    version: int
    providers: Providers = Providers()
    tasks: dict[str, TaskRoute]
    prices: dict[str, Price] = {}

    def route(self, task: str) -> TaskRoute:
        try:
            return self.tasks[task]
        except KeyError:
            raise KeyError(f"task {task!r} is not in {ROUTING_FILE}") from None

    def cost(self, model: str, usage: Usage) -> float:
        price = self.prices.get(model)
        return price.cost(usage) if price is not None else 0.0


def find_routing_file(start: Path | None = None) -> Path:
    """`LLM_ROUTING_FILE` if set, else the nearest `llm_routing.yaml` above the working
    directory or above this package (the repository root)."""
    explicit = os.environ.get("LLM_ROUTING_FILE")
    if explicit:
        return Path(explicit)
    for base in (start or Path.cwd(), Path(__file__).resolve()):
        for folder in (base, *base.parents):
            candidate = folder / ROUTING_FILE
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(f"{ROUTING_FILE} not found (set LLM_ROUTING_FILE)")


def parse_routing(text: str) -> Routing:
    return Routing.model_validate(yaml.safe_load(text))


@lru_cache
def load_routing(path: Path | None = None) -> Routing:
    return parse_routing((path or find_routing_file()).read_text(encoding="utf-8"))
