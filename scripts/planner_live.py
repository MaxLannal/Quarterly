"""A live run of the planner agent (issues #17 and #18) on a real model. COSTS MONEY.

    LLM_LIVE=true uv run python scripts/planner_live.py --student cs-first-year --confirm-spend
    ... --student cs-first-year --chat "I hate Language and the Human. Suggest a new Core."

The students are invented fixtures (no real person's data). The run uses a throwaway database
on the DATABASE_URL server with the 2026-27 seed, the real gateway (ANTHROPIC_API_KEY and the
optional ANTHROPIC_BASE_URL, e.g. Teamorouter, from the environment), and prints the steps,
the verdict, each group with its reason, the seconds and the cost at list prices. It refuses
to run without --confirm-spend and LLM_LIVE=true, and stops when the running total in
--ledger passes --cap (USD).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed" / "2026-27"

STUDENTS: dict[str, dict[str, Any]] = {
    "cs-first-year": {
        "plan": {
            "catalog_year": "2026-27",
            "entry_term": "2026-AU",
            "placements": ["MATH 15100"],
            "programs": [{"program_id": "core"}, {"program_id": "cmsc-bs"}],
        },
        "answers": {
            "interests": ["machine learning", "philosophy of mind"],
            "post_grad_plan": "industry",
            "pace": "on_time",
            "course_load": "normal",
            "theory_vs_application": 6,
        },
    },
    "cs-first-year-theory": {
        "plan": {
            "catalog_year": "2026-27",
            "entry_term": "2026-AU",
            "placements": ["MATH 15100"],
            "programs": [{"program_id": "core"}, {"program_id": "cmsc-ba"}],
        },
        "answers": {
            "interests": ["algorithms", "cryptography", "music"],
            "post_grad_plan": "grad_school",
            "wants_research": True,
            "research_areas": ["theory of computation"],
            "course_load": "normal",
            "theory_vs_application": 2,
        },
    },
    "cs-transfer": {
        "plan": {
            "catalog_year": "2026-27",
            "entry_term": "2026-AU",
            "entry_year_level": 2,
            "placements": ["MATH 15100"],
            "programs": [{"program_id": "core"}, {"program_id": "cmsc-bs"}],
            "items": [
                {"course": "CMSC 14100", "term": "2026-AU", "status": "completed"},
                {"course": "MATH 15100", "term": "2026-AU", "status": "completed"},
            ],
        },
        "answers": {
            "interests": ["data science", "economics"],
            "post_grad_plan": "industry",
            "course_load": "conservative",
            "theory_vs_application": 8,
        },
    },
}


@contextmanager
def throwaway_db() -> Iterator[Any]:
    from alembic import command
    from alembic.config import Config
    from api.config import get_settings
    from api.seed.bundle import load_bundle
    from api.seed.loader import upsert_bundle
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    base = make_url(get_settings().database_url)
    name = f"qp_live_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    engine = create_engine(url)
    try:
        cfg = Config(str(ROOT / "services" / "api" / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(cfg, "head")
        with Session(engine) as db:
            upsert_bundle(db, load_bundle(SEED))
            db.commit()
        with Session(engine) as db:
            yield db
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def gateway() -> Any:
    from api.config import get_settings
    from llm_gateway.gateway import build_gateway

    s = get_settings()
    gw = build_gateway(
        anthropic_api_key=s.anthropic_api_key.get_secret_value(),
        openrouter_api_key=s.openrouter_api_key.get_secret_value(),
        anthropic_base_url=s.anthropic_base_url or None,
    )
    if gw is None:
        raise SystemExit("no provider key in the environment")
    return gw


def tally() -> Any:
    """A RunLog that keeps the run's total after `save` clears its records."""
    from api.agents.runtime import RunLog

    class Tally(RunLog):
        total: float = 0.0
        calls: int = 0

        def sink(self, record: Any) -> None:
            super().sink(record)
            self.total += record.cost_usd
            self.calls += 1

    return Tally()


def show(event: dict[str, Any]) -> None:
    kind = event["type"]
    if kind == "step":
        print(f"  step  {event['status']:<7} {event['name']}")
    elif kind == "plan":
        errors = [i for i in event["issues"] if i["level"] == "error"]
        warnings = len(event["issues"]) - len(errors)
        print(
            f"  PLAN  verdict={event['verdict']} errors={len(errors)} warnings={warnings} "
            f"compromises={len(event['compromises'])}"
        )
        for i in errors[:8]:
            print(f"        {i['code']} {i['message'][:140]}")
        for c in event["compromises"][:6]:
            print(f"        bent {c['rule']} ({c['tier']}): {c['why'][:120]}")
    elif kind == "proposal":
        courses = ", ".join(
            f"{o.get('course')} {o.get('term') or o.get('to_term') or ''}".strip()
            for o in event["ops"]
        )
        cites = ", ".join(f"{c['kind']}:{c['id']}" for c in event["citations"])
        rules = ", ".join(r["id"] for r in event["rules"])
        print(
            f"  GROUP [{event['kind']}] {event['title']}\n        {courses}\n"
            f"        why: {event['why']}\n        rules: {rules or '-'}  cites: {cites or '-'}"
        )
    elif kind == "question":
        print(f"  QUESTION {event['text']} {event['options']}")
    elif kind == "message":
        print(f"  MESSAGE {event['text']}")
    elif kind == "error":
        print(f"  ERROR {event.get('reason')}: {event['message']}")
    elif kind == "done":
        print(f"  done  working_notes={event.get('working_notes')!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A live run of the planner agent.")
    parser.add_argument("--student", choices=sorted(STUDENTS), required=True)
    parser.add_argument("--chat", help="after the plan, one chat message")
    parser.add_argument("--confirm-spend", action="store_true")
    parser.add_argument("--cap", type=float, default=15.0)
    parser.add_argument("--ledger", type=Path, default=Path("planner_live_ledger.json"))
    args = parser.parse_args(argv)
    if not args.confirm_spend or os.environ.get("LLM_LIVE", "").lower() != "true":
        print("refusing: pass --confirm-spend and set LLM_LIVE=true (costs money)", file=sys.stderr)
        return 2
    spent = json.loads(args.ledger.read_text())["usd"] if args.ledger.exists() else 0.0
    if spent >= args.cap:
        print(f"refusing: ${spent:.2f} spent already (cap ${args.cap:.2f})", file=sys.stderr)
        return 2

    from api.agents.planner.chat import PlannerChat
    from api.agents.planner.harness import PlannerRun
    from api.repo import catalog as catalog_repo
    from api.schemas.planner import PlannerRequest, QuestionAnswer
    from planner_core.changes import apply_ops
    from planner_core.models import ChangeOp
    from pydantic import TypeAdapter

    student = STUDENTS[args.student]
    llm = gateway()
    total = 0.0
    statuses = catalog_repo.ALL_STATUSES
    with throwaway_db() as db:
        req = PlannerRequest.model_validate(
            {"mode": "generate", "plan": student["plan"], "profile_answers": student["answers"]}
        )
        log = tally()
        start = time.monotonic()
        run = PlannerRun.build(
            db, llm, req, account=None, saved=None, show_unpublished=True, statuses=statuses,
            log=log,
        )  # fmt: skip
        print(f"== generate: {args.student}")
        ops: list[Any] = []
        for _ in range(4):  # a run pauses for each question; answer it with its first option
            question = None
            for event in run.generate_events():
                data = event.model_dump(mode="json")
                show(data)
                if data["type"] == "proposal":
                    ops += data["ops"]
                if data["type"] == "question":
                    question = data
            if question is None:
                break
            option = question["options"][0] if question["options"] else None
            print(f"  ANSWER {option or 'machine learning'}")
            answer = {"question_id": question["question_id"], "option": option}
            if not option:
                answer["text"] = "machine learning"
            req = req.model_copy(
                update={
                    "run_id": uuid.UUID(question["run_id"]),
                    "answer": QuestionAnswer.model_validate(answer),
                }
            )
            run = PlannerRun.build(
                db, llm, req, account=None, saved=None, show_unpublished=True,
                statuses=statuses, log=log,
            )  # fmt: skip
        total += log.total
        print(f"== {time.monotonic() - start:.0f} s, ${log.total:.2f}, {log.calls} model calls")
        if args.chat:
            plan = apply_ops(req.plan, TypeAdapter(list[ChangeOp]).validate_python(ops))
            chat_req = PlannerRequest.model_validate(
                {
                    "mode": "chat",
                    "plan": plan.model_dump(mode="json"),
                    "message": args.chat,
                    "profile_answers": student["answers"],
                }
            )
            chat_log = tally()
            start = time.monotonic()
            chat = PlannerChat(
                db=db, llm=llm, req=chat_req, show_unpublished=True, statuses=statuses,
                log=chat_log,
            )  # fmt: skip
            print(f"== chat: {args.chat}")
            for event in chat.events():
                show(event.model_dump(mode="json"))
            total += chat_log.total
            print(f"== {time.monotonic() - start:.0f} s, ${chat_log.total:.2f}")
    args.ledger.write_text(json.dumps({"usd": round(spent + total, 4)}))
    print(f"== this run ${total:.2f}; total ${spent + total:.2f} of ${args.cap:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
