"""The planner agent, generate mode (issue #17): a port of the degree-plan-agent harness
(ZhihchengGao/degree-plan-agent, `src/qplan/harness.py`) onto `llm_gateway` and `planner_core`.

    read -> ask (question file, then the model) -> fill -> check -> repair* -> explain -> return

- Code owns the phases, the budgets, the state and the verdict. The model proposes questions,
  a grouped plan, repairs and explanations through submit tools.
- A plan is valid only when `verify_checked` reports no errors and the certificate checker
  accepts it (CLAUDE.md hard rule); the student's own standards (S01-S03) are errors too.
- Each group of the final plan becomes one proposal (a `change_set` for a saved plan). The
  agent writes nothing else: answers to questions become `profile_proposal` rows.
- Before a question the run state is saved in `agent_run.state` and the stream ends; the next
  request with `run_id` + `answer` continues from it.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass, field
from typing import Any

from llm_gateway.api import run_agent
from llm_gateway.types import AgentError, AgentSpec, Budget, Message, SubmitTool
from planner_core import verify_checked
from planner_core.changes import ChangeOpError, apply_ops
from planner_core.generator import generate, horizon
from planner_core.hashing import plan_hash
from planner_core.models import (
    AddOp,
    Catalog,
    ChangeOp,
    Credit,
    GenerateOptions,
    MoveOp,
    PlanItem,
    PlanState,
    RemoveOp,
    RuleSet,
)
from planner_core.terms import term_key
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.agents.interview import split_items
from api.agents.planner.brief import known_codes, math_placements, requirements_brief
from api.agents.planner.guideline import PlannerConfig, load_guideline, load_planner_config
from api.agents.planner.standards import standard_issues, standards_from
from api.agents.planner.state import (
    AskedQuestion,
    ExplanationsSubmission,
    PlanSubmission,
    QuestionsSubmission,
    RepairSubmission,
    RunState,
)
from api.agents.prompts import load_prompt
from api.agents.runtime import RunLog, checked_citations, citable_ids, new_run, split_ref
from api.agents.tools import ToolBox
from api.config import get_settings
from api.db import models as m
from api.profile_data import ensure_profile, profile_out, render_student_md
from api.profile_questions import Question, question_set
from api.repo import plans as plans_repo
from api.repo.rules import load_verify_inputs
from api.schemas.agents import DoneEvent, ErrorEvent, MessageEvent, StepEvent
from api.schemas.planner import (
    Compromise,
    PlanEvent,
    PlanIssue,
    PlannerProposalEvent,
    PlannerRequest,
    QuestionAnswer,
    QuestionEvent,
    RuleRef,
    Verdict,
)

logger = logging.getLogger("api.agents")

TASK = "a1_planner_agent"
KIND = "planner"
STEP_READ = "Reading your information"
STEP_FIT = "Checking what can fit"
STEP_WRITE = "Writing your plan"
STEP_CHECK = "Checking the plan"
STEP_FIX = "Fixing the plan (round {n})"
STEP_EXPLAIN = "Explaining each choice"

NO_MAJOR = "Choose your major first: use + Program above your plan. Then press Generate plan again."
UNAVAILABLE = "The planner can't write a plan right now. You can still build your plan by hand."
EXPIRED = "This question has expired. Press Generate plan to start again."
NO_RUN = "This run was not found. Press Generate plan to start again."
#: General Information answers a first plan needs (a missing one is asked before planning).
REQUIRED_FIELDS = ("interests",)
#: The math placement, asked before planning when the plan has none (live, 2026-11-26: without
#: it no calculus course can be planned, so the CS BS was impossible and the writing step failed).
PLACEMENT_ID = "placement"
PLACEMENT_TEXT = (
    "Which math course did the UChicago math placement put you in? Your plan starts there."
)
NOT_YET = "I have not taken the placement yet"
PLACEMENT_ASSUMED = (
    "You have not taken the math placement yet, so this plan starts at {code}, the lowest of "
    "the placements these requirements accept. When you have your result, change it under "
    "Credits and press Generate plan again."
)
REPLACE_TITLE = "Courses this plan replaces"
REPLACE_WHY = "The new plan does not keep these courses. Reject this to keep them."
SOLVER_SECONDS = 4.0
WRITE_TOKENS = 400_000
STEP_TOKENS = 200_000
#: The order of groups in the walkthrough and the proposal list.
KIND_ORDER = {"major": 0, "core": 1, "minor": 2, "elective": 3, "other": 4, "replace": 5}
READ_TOOLS = ["search_courses", "get_course", "get_forum_summary", "get_forum_posts"]


def _plain(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _detail(exc: Exception) -> str:
    """What a failed step's check or schema rejected: catalog codes, quarters and field names
    from the agent's own output, never the student's record."""
    return str(exc)[:500]


def coerce_answer(question: Question, value: Any) -> Any:
    """A General Information answer from a question card ({option, text}) or a browser plan
    (already a stored value), as the field stores it. None when it cannot be read."""
    if isinstance(value, QuestionAnswer):
        value = value.model_dump()
    if isinstance(value, dict) and ("option" in value or "text" in value):
        option, text = value.get("option"), value.get("text")
        if question.type == "list":
            items = split_items(" , ".join(x for x in (option, text) if x))
            return [i[:1].upper() + i[1:] for i in items] or None
        if question.options:
            for o in question.options:
                if option and option.strip().lower() in (o.label.lower(), str(o.value).lower()):
                    return o.value
            return None
        return (text or option or "").strip() or None
    return value


def _answered(value: Any) -> bool:
    return value not in (None, "", [], {})


@dataclass
class Group:
    id: str
    title: str
    kind: str
    why: str
    rules: list[str]
    placements: list[tuple[str, str]]  # (course, term)


@dataclass
class PlannerRun:
    db: Session
    llm: object
    req: PlannerRequest
    rules: RuleSet
    catalog: Catalog
    box: ToolBox
    log: RunLog
    account: m.Account | None = None
    saved: m.Plan | None = None
    config: PlannerConfig = field(default_factory=load_planner_config)
    today: dt.date = field(default_factory=dt.date.today)
    #: The math placement this run plans with (the student's answer); the page adds it.
    placements: list[str] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        db: Session,
        llm: object,
        req: PlannerRequest,
        *,
        account: m.Account | None,
        saved: m.Plan | None,
        show_unpublished: bool,
        statuses: tuple[str, ...],
        log: RunLog,
        config: PlannerConfig | None = None,
    ) -> PlannerRun:
        """Load the catalog and rules for the request's plan (raises UnknownProgramsError)."""
        rules, catalog = load_verify_inputs(
            db,
            req.plan,
            show_unpublished=show_unpublished,
            whole_catalog=True,
            section_terms=horizon(req.plan),
        )
        report, _ = verify_checked(req.plan, rules, catalog)
        box = ToolBox(
            db=db,
            state=req.plan,
            report=report,
            statuses=statuses,
            show_unpublished=show_unpublished,
            logged_in=account is not None,
        )
        return cls(
            db=db,
            llm=llm,
            req=req,
            rules=rules,
            catalog=catalog,
            box=box,
            log=log,
            account=account,
            saved=saved,
            config=config or load_planner_config(),
        )

    # ------------------------------------------------------------------------ inputs

    def step(self, name: str, status: str) -> StepEvent:
        self.log.step(name, status)
        return StepEvent.model_validate({"name": name, "status": status})

    def record(self, state: RunState) -> dict[str, Any]:
        """The General Information answers: the saved record, or the browser plan's answers,
        plus the answers given in this run."""
        qs = {q.field: q for q in question_set().questions}
        if self.account is not None:
            row = ensure_profile(self.db, self.account.id)
            out = _plain(profile_out(self.db, self.account, row))
        else:
            out = {
                f: coerce_answer(qs[f], v) for f, v in self.req.profile_answers.items() if f in qs
            }
        for asked in state.asked:
            answer = state.answers.get(asked.question_id)
            if asked.field and answer is not None and asked.field in qs:
                value = coerce_answer(qs[asked.field], answer)
                if value is not None:
                    out[asked.field] = value
        return out

    def working_notes(self) -> str:
        if self.account is not None:
            row = ensure_profile(self.db, self.account.id)
            return (row.working_notes or "").strip()
        return (self.req.working_notes or "").strip()

    def student_md(self, record: dict[str, Any]) -> str:
        if self.account is not None:
            row = ensure_profile(self.db, self.account.id)
            with self.db.no_autoflush:
                for f in REQUIRED_FIELDS:  # an answer of this run is not in the record yet
                    if f in record and not getattr(row, f, None):
                        setattr(row, f, record[f])
                text = render_student_md(self.db, row, grades=False)
            self.db.expire(row)  # never save the run's answers into the record
            return text
        row = m.StudentProfile()
        for q in question_set().questions:
            if q.type == "list":
                setattr(row, q.field, list(record.get(q.field) or []))
            elif q.type != "table" and hasattr(row, q.field):
                setattr(row, q.field, record.get(q.field))
        row.terms_away = record.get("terms_away")
        with self.db.no_autoflush:
            return render_student_md(self.db, row, grades=False)

    def terms(self) -> list[str]:
        terms = horizon(self.req.plan)
        if self.req.today_term:
            terms = [t for t in terms if term_key(t) >= term_key(self.req.today_term)]
        return terms

    def has_major(self) -> bool:
        return any(p.program_id != "core" for p in self.req.plan.programs or [])

    def fixed_items(self) -> list[PlanItem]:
        """Items the agent never moves: completed, in progress and locked."""
        return [i for i in self.req.plan.items or [] if i.status != "planned" or i.locked]

    def open_items(self) -> list[PlanItem]:
        return [i for i in self.req.plan.items or [] if i.status == "planned" and not i.locked]

    def state_of(self, groups: list[Group]) -> PlanState:
        fixed = self.fixed_items()
        fixed_codes = {(i.course, i.term) for i in fixed}
        items = list(fixed) + [
            PlanItem(course=c, term=t)
            for g in groups
            for c, t in g.placements
            if (c, t) not in fixed_codes
        ]
        return self.req.plan.model_copy(update={"items": items})

    def check(self, state: PlanState, record: dict[str, Any]) -> tuple[bool, list[PlanIssue]]:
        """Valid only with no verifier error, an accepted certificate and no broken standard."""
        report, problems = verify_checked(state, self.rules, self.catalog)
        extra = standard_issues(state, self.catalog, standards_from(record, self.working_notes()))
        issues = [
            PlanIssue(
                code=i.code,
                level=i.level,
                message=i.message,
                course_ids=list(i.course_ids),
                term_ids=list(i.term_ids),
            )
            for i in report.issues
            if i.level in ("error", "warning")
        ] + extra
        valid = (
            not problems
            and report.certificate is not None
            and report.status != "errors"
            and not extra
        )
        return valid, issues

    def known_ids(self, record: dict[str, Any]) -> set[str]:
        fields = {f for f, v in record.items() if _answered(v)}
        ids = citable_ids(profile_fields=fields, guideline_ids=load_guideline().rules)
        return ids | {f"course:{i.course}" for i in self.req.plan.items or [] if i.course}

    def system(self, brief: str) -> str:
        prompt = load_prompt("a1_planner")
        return (
            f"{prompt.text}\n\n# Plan guideline\n\n{load_guideline().text}\n\n"
            f"# Requirements brief\n\n{brief}\n"
        )

    def spec[T: BaseModel](
        self,
        system: str,
        user: str,
        submit: tuple[str, str, type[T]],
        record: dict[str, Any],
        *,
        check: Callable[[T], None] | None = None,
        tools: bool = True,
        tokens: int = STEP_TOKENS,
        seconds: int | None = None,
    ) -> AgentSpec[T]:
        name, description, model = submit
        return AgentSpec(
            task=TASK,
            prompt_version=load_prompt("a1_planner").version_tag,
            system=system,
            messages=[Message("user", user)],
            submit=SubmitTool(name, description, model, check=check),
            tools=self.box.tools(READ_TOOLS) if tools else [],
            budget=Budget(
                tool_calls=self.config.tool_calls_per_step,
                tokens=tokens,
                seconds=seconds or self.config.run_seconds,
            ),
            known_ids=self.known_ids(record),
        )

    # ------------------------------------------------------------------------ run state

    def _load_run(self) -> tuple[m.AgentRun, RunState] | ErrorEvent:
        if self.req.run_id is None:
            run = new_run(self.db, KIND, self.saved.id if self.saved else None)
            return run, RunState(day=self.today)
        found = self.db.get(m.AgentRun, self.req.run_id)
        if found is None or found.kind != KIND or found.state is None:
            return ErrorEvent(message=NO_RUN, reason="expired")
        state = RunState.model_validate(found.state)
        if (self.today - state.day).days > self.config.state_ttl_days:
            found.state = None
            self.db.commit()
            return ErrorEvent(message=EXPIRED, reason="expired")
        if self.req.answer is not None:
            state.answers[self.req.answer.question_id] = self.req.answer
            self._propose_profile_answer(state, self.req.answer)
        return found, state

    def _propose_profile_answer(self, state: RunState, answer: QuestionAnswer) -> None:
        asked = next((a for a in state.asked if a.question_id == answer.question_id), None)
        if asked is None or asked.field is None or self.account is None:
            return
        question = next(q for q in question_set().questions if q.field == asked.field)
        value = coerce_answer(question, answer)
        if value is None:
            return
        self.db.add(
            m.ProfileProposal(
                account_id=self.account.id,
                field=asked.field,
                value=value,
                source="planner_chat",
                status="proposed",
                created_day=self.today,
            )
        )

    def _pause(self, run: m.AgentRun, state: RunState, asked: AskedQuestion) -> Iterator[BaseModel]:
        state.asked = [a for a in state.asked if a.question_id != asked.question_id] + [asked]
        run.state = _plain(state)
        run.status = "waiting"
        self.log.save(self.db, run)
        self.db.commit()
        yield QuestionEvent(
            run_id=str(run.id),
            question_id=asked.question_id,
            field=asked.field,
            text=asked.text,
            options=asked.options,
        )
        yield DoneEvent(run_id=str(run.id), placements=self.placements or None)

    def _finish(
        self,
        run: m.AgentRun,
        last: BaseModel | None,
        *,
        status: str,
        profile_answers: dict[str, Any] | None = None,
    ) -> Iterator[BaseModel]:
        if last is not None:
            yield last
        run.state = None
        run.status = status[:16]
        self.log.save(self.db, run)
        self.db.commit()
        yield DoneEvent(
            run_id=str(run.id),
            profile_answers=profile_answers,
            placements=self.placements or None,
        )

    # ------------------------------------------------------------------------ phases

    def _missing_question(self, state: RunState, record: dict[str, Any]) -> AskedQuestion | None:
        for f in REQUIRED_FIELDS:
            if _answered(record.get(f)) or f in state.answers:
                continue  # answered, or asked and answered with nothing usable: ask once
            q = next(q for q in question_set().questions if q.field == f)
            return AskedQuestion(
                question_id=q.id, field=q.field, text=q.text, options=[o.label for o in q.options]
            )
        return None

    def _placement_question(self, state: RunState) -> AskedQuestion | None:
        if PLACEMENT_ID in state.answers or state.placements:
            return None
        report, _ = verify_checked(self.req.plan, self.rules, self.catalog)
        codes = math_placements(self.req.plan, self.rules, self.catalog, report)
        if not codes:
            return None
        titles = {c.code: c.title for c in self.catalog.courses}
        options = [f"{c} ({titles[c]})" if titles.get(c) else c for c in codes]
        return AskedQuestion(
            question_id=PLACEMENT_ID, text=PLACEMENT_TEXT, options=[*options, NOT_YET]
        )

    def _take_placement(self, state: RunState) -> MessageEvent | None:
        """The placement answer as a course code, once. "Not yet" (or an answer that names no
        offered placement) plans from the lowest one and says so (strict reading: a course
        that needs a placement is never planned without one)."""
        answer = state.answers.get(PLACEMENT_ID)
        asked = next((a for a in state.asked if a.question_id == PLACEMENT_ID), None)
        if answer is None or asked is None or state.placements:
            return None
        codes = [" ".join(o.split()[:2]) for o in asked.options if o != NOT_YET]
        said = f"{answer.option or ''} {answer.text or ''}"
        numbers = set(re.findall(r"\b\d{5}\b", said))
        picked = next((c for c in codes if c.split()[-1] in numbers), None)
        if picked is not None:
            state.placements = [picked]
            return None
        if not codes:
            return None
        state.placements = [codes[0]]
        return MessageEvent(text=PLACEMENT_ASSUMED.format(code=codes[0]))

    def _use_placements(self, state: RunState) -> None:
        """Plan with the student's placement: the run's plan gets it as a placement credit, the
        same credit the page adds, so the proposals fit the page's plan (`base_plan_hash`)."""
        self.placements = list(state.placements)
        plan = self.req.plan
        have = set(plan.placements) | {c.label for c in plan.credits if c.kind == "placement"}
        extra = [c for c in state.placements if c not in have]
        if not extra:
            return
        credits = [*plan.credits, *(Credit(kind="placement", label=c) for c in extra)]
        plan = plan.model_copy(update={"credits": credits})
        self.req = self.req.model_copy(update={"plan": plan})
        self.box.state = plan

    def _model_questions(
        self, system: str, user: str, record: dict[str, Any]
    ) -> list[AskedQuestion]:
        if self.config.questions_max <= 0:
            return []
        task = (
            "Before planning, decide what to ask this student. Ask only when the answer would "
            "change a decision in the plan that the record cannot settle; name that decision. "
            f"Write at most {self.config.questions_max} multiple-choice questions (zero is "
            f"best when the record is enough), each with {self.config.min_options}-"
            f"{self.config.max_options} options; the page adds an 'Other' box. "
            "Call submit_questions."
        )
        submit = (
            "submit_questions",
            "Submit the questions to ask before planning (possibly none).",
            QuestionsSubmission,
        )
        spec = self.spec(system, f"{user}\n\n# Task\n\n{task}", submit, record, tools=False)
        out = run_agent(self.llm, spec, sink=self.log.sink).output
        asked = []
        for i, q in enumerate(out.questions[: self.config.questions_max], 1):
            options = [o for o in q.options if o.strip()][: self.config.max_options]
            if len(options) >= self.config.min_options:
                asked.append(AskedQuestion(question_id=f"Q{i}", text=q.question, options=options))
        return asked

    def _user_text(self, record: dict[str, Any], state: RunState, feasibility: str) -> str:
        notes = self.working_notes()
        if len(notes) > self.config.working_info_chars:
            words = {str(w).lower() for v in record.values() if isinstance(v, list) for w in v}
            notes = "\n".join(
                ln for ln in notes.splitlines() if any(w in ln.lower() for w in words)
            )[: self.config.working_info_chars]
        fixed = ", ".join(
            f"{i.course} {i.term} ({i.status})" for i in self.fixed_items() if i.course
        )
        plan = self.req.plan
        placements = ", ".join(plan.placements or []) or "none"
        credits = "; ".join(
            f"{c.label or c.kind}" + (f" = {c.maps_to}" if c.maps_to else "")
            for c in plan.credits or []
        )
        movable = ", ".join(f"{i.course} {i.term}" for i in self.open_items() if i.course)
        answers = []
        for a in state.asked:
            given = state.answers.get(a.question_id)
            if given is not None:
                answers.append(f"- {a.question_id} {a.text}: {given.option or given.text or '-'}")
        return "\n\n".join(
            [
                "# The student's record (student.md)\n\n" + self.student_md(record),
                "# Working information (from earlier chats)\n\n" + (notes or "None yet."),
                "# Quarters to plan\n\n" + ", ".join(self.terms()),
                "# The plan now\n\n"
                f"Completed, in progress or locked (keep): {fixed or 'none'}\n"
                f"Planned, not locked (keep, move or drop): {movable or 'none'}\n"
                f"Placements (already decided by the College's tests): {placements}\n"
                f"Credits: {credits or 'none'}",
                "# Feasibility (Quarterly's solver as an oracle; its plan is not used)\n\n"
                + feasibility,
                "# Answers to questions\n\n" + ("\n".join(answers) or "None."),
            ]
        )

    def _feasibility(self) -> tuple[str, MessageEvent | None]:
        """The solver as an oracle: a line for the model and, for an impossible request, a
        message to the student naming the rules in conflict (SPEC journey B)."""
        try:
            seconds = get_settings().generate_solver_seconds or SOLVER_SECONDS
            options = GenerateOptions(
                variants=1, time_limit_s=seconds, today_term=self.req.today_term
            )
            result = generate(self.req.plan, self.rules, self.catalog, options)
        except Exception:  # the oracle is advice; the run goes on without it
            logger.exception("%s: feasibility oracle failed", TASK)
            return "Not checked.", None
        if result.variants:
            return "A valid plan exists for these programs in these quarters.", None
        if result.infeasible is None:
            return "Not settled within the time limit.", None
        proof = result.infeasible
        rules = "; ".join(c.label for c in proof.conflicts)
        conflict = f" The rules in conflict: {rules}." if rules else ""
        notice = MessageEvent(
            text=f"No plan fits all of these rules. {proof.message}{conflict} I will still "
            "write the closest plan; the plan check shows what is missing."
        )
        return f"No valid plan was found: {proof.message}{conflict}", notice

    def _fill_problems(self) -> Callable[[PlanSubmission], list[tuple[int, int, str]]]:
        """(group index, course index, problem) of every course the plan cannot take: an
        unknown code, a quarter that is not planned, a completed course, a locked or in-progress
        course moved, a course already in an earlier group."""
        known = known_codes(self.req.plan, self.catalog)
        terms = set(self.terms())
        done = {i.course for i in self.req.plan.items or [] if i.status == "completed"}
        fixed = {
            i.course: i.term for i in self.fixed_items() if i.course and i.status != "completed"
        }

        def problems(sub: PlanSubmission) -> list[tuple[int, int, str]]:
            out: list[tuple[int, int, str]] = []
            seen: dict[str, str] = {}
            for gi, g in enumerate(sub.groups):
                for ci, c in enumerate(g.courses):
                    if c.code in fixed and fixed[c.code] != c.term:
                        moved = f"{c.code} is locked or in progress in {fixed[c.code]}; leave it"
                        out.append((gi, ci, moved))
                    if c.code not in known:
                        out.append((gi, ci, f"{c.code} is not a course in the catalog"))
                    if c.term not in terms:
                        out.append((gi, ci, f"{c.term} is not one of the quarters to plan"))
                    if c.code in done:
                        out.append((gi, ci, f"{c.code} is already completed"))
                    if c.code in seen and seen[c.code] != g.id:
                        out.append((gi, ci, f"{c.code} is in two groups ({seen[c.code]}, {g.id})"))
                    seen.setdefault(c.code, g.id)
            return out

        return problems

    def _fill_check(self) -> Callable[[PlanSubmission], None]:
        """Reject a plan with problems once, so the model can fix them; a second plan with
        problems passes, and `_kept` drops the courses at fault (live, 2026-11-27: a second
        rejection threw away the whole plan, which the verifier and the repairs could finish)."""
        problems = self._fill_problems()
        rejected = False

        def check(sub: PlanSubmission) -> None:
            nonlocal rejected
            found = problems(sub)
            if found and not rejected:
                rejected = True
                text = "; ".join(sorted({m for _, _, m in found}))
                raise ValueError("Fix these and submit again: " + text)

        return check

    def _kept(self, sub: PlanSubmission) -> PlanSubmission:
        """The plan without the courses the check still rejects (none, normally)."""
        found = self._fill_problems()(sub)
        if not found:
            return sub
        drop = {(gi, ci) for gi, ci, _ in found}
        groups = []
        for gi, g in enumerate(sub.groups):
            courses = [c for ci, c in enumerate(g.courses) if (gi, ci) not in drop]
            if courses:
                groups.append(g.model_copy(update={"courses": courses}))
        reasons = "; ".join(sorted({m for _, _, m in found}))
        logger.warning("%s: kept the plan without %d course(s): %s", TASK, len(drop), reasons[:500])
        return sub.model_copy(update={"groups": groups})

    def _repair_check(self) -> Callable[[RepairSubmission], None]:
        """A repair is checked like a fill: real codes, quarters of the plan, nothing completed,
        locked or in progress moved (final review: an unchecked op crashed the run)."""
        known = known_codes(self.req.plan, self.catalog)
        terms = set(self.terms())
        fixed = {i.course for i in self.fixed_items() if i.course}

        def check(sub: RepairSubmission) -> None:
            problems: set[str] = set()
            for op in sub.ops:
                if op.course not in known:
                    problems.add(f"{op.course} is not a course in the catalog")
                if op.course in fixed:
                    problems.add(f"{op.course} is completed, locked or in progress; leave it")
                target = op.term or op.to_term
                if op.op in ("add", "move") and target not in terms:
                    problems.add(f"{op.op} {op.course}: give one of the quarters to plan")
            if problems:
                raise ValueError("Fix these and submit again: " + "; ".join(sorted(problems)))

        return check

    def _apply_repair(self, groups: list[Group], sub: RepairSubmission) -> list[str]:
        notes: list[str] = []
        for op in sub.ops[: self.config.max_ops_per_round]:
            owner = next((g for g in groups if any(c == op.course for c, _ in g.placements)), None)
            if op.op == "add":
                target = next((g for g in groups if g.id == op.group_id), None) or owner
                if target is None:
                    gid = op.group_id or f"r{len(groups) + 1}"
                    target = Group(gid, "Other courses", "other", "", [], [])
                    groups.append(target)
                target.placements.append((op.course, op.term or op.to_term))
            elif owner is None:
                notes.append(f"skipped {op.op} {op.course}: it is not in the plan")
            elif op.op == "move":
                to, frm = op.to_term or op.term, op.from_term
                owner.placements = [
                    (c, to if c == op.course and (not frm or t == frm) else t)
                    for c, t in owner.placements
                ]
            else:
                owner.placements = [(c, t) for c, t in owner.placements if c != op.course]
        for g in [g for g in groups if not g.placements]:
            groups.remove(g)
        return notes

    def _grid(self, groups: list[Group]) -> str:
        by_term: dict[str, list[str]] = {}
        for g in groups:
            for c, t in g.placements:
                by_term.setdefault(t, []).append(f"{c} ({g.id})")
        for i in self.fixed_items():
            if i.course:
                by_term.setdefault(i.term, []).append(f"{i.course} ({i.status}, fixed)")
        rows = sorted(by_term.items(), key=lambda kv: term_key(kv[0]))
        return "\n".join(f"- {t}: {', '.join(v)}" for t, v in rows)

    @staticmethod
    def _issues_text(issues: list[PlanIssue]) -> str:
        rows = sorted(issues, key=lambda i: (i.level != "error", i.code))[:25]
        return json.dumps([_plain(i) for i in rows], ensure_ascii=False)

    def _ops_for(self, group: Group) -> list[ChangeOp]:
        """The group as ops on the request plan: add new placements, move an unlocked item of
        the same course."""
        open_by_course = {i.course: i for i in self.open_items() if i.course}
        fixed = {i.course for i in self.fixed_items() if i.course}
        ops: list[ChangeOp] = []
        for code, term in group.placements:
            if code in fixed:  # completed, locked or in progress: never added again
                continue
            current = open_by_course.get(code)
            if current is None:
                ops.append(AddOp(course=code, term=term))
            elif current.term != term:
                ops.append(MoveOp(course=code, from_term=current.term, to_term=term))
        return ops

    def _removals(self, groups: list[Group]) -> list[ChangeOp]:
        kept = {c for g in groups for c, _ in g.placements}
        return [
            RemoveOp(course=i.course, term=i.term)
            for i in self.open_items()
            if i.course and i.course not in kept
        ]

    def _verdict(self, ops: list[ChangeOp]) -> Verdict | None:
        try:
            after = apply_ops(self.req.plan, ops)
        except ChangeOpError:
            return None
        report, _ = verify_checked(after, self.rules, self.catalog)
        return Verdict.model_validate(self.box._verdict(report))

    # ------------------------------------------------------------------------ the run

    def generate_events(self) -> Iterator[BaseModel]:
        loaded = self._load_run()
        if isinstance(loaded, ErrorEvent):
            yield loaded
            return
        run, state = loaded
        assumed = self._take_placement(state)
        self._use_placements(state)
        yield self.step(STEP_READ, "started")
        record = self.record(state)
        yield self.step(STEP_READ, "done")

        if not self.has_major():
            yield from self._finish(run, MessageEvent(text=NO_MAJOR), status="no_major")
            return
        missing = self._missing_question(state, record) or self._placement_question(state)
        if missing is not None:
            yield from self._pause(run, state, missing)
            return
        if assumed is not None:
            yield assumed

        yield self.step(STEP_FIT, "started")
        feasibility, impossible = self._feasibility()
        report, _ = verify_checked(self.req.plan, self.rules, self.catalog)
        system = self.system(requirements_brief(self.req.plan, self.rules, self.catalog, report))
        yield self.step(STEP_FIT, "done")
        if impossible is not None:
            yield impossible

        if not state.model_asked:
            state.model_asked = True
            try:
                user = self._user_text(record, state, feasibility)
                asked = self._model_questions(system, user, record)
            except AgentError as exc:
                logger.warning("%s: questions step failed (%s): %s", TASK, exc.reason, _detail(exc))
                asked = []
            if asked:
                state.asked += asked[1:]  # the rest wait their turn
                yield from self._pause(run, state, asked[0])
                return
        pending = next((a for a in state.asked if a.question_id not in state.answers), None)
        if pending is not None:
            yield from self._pause(run, state, pending)
            return

        user = self._user_text(record, state, feasibility)
        yield self.step(STEP_WRITE, "started")
        task = (
            "Fill every quarter of the plan in one submit_plan call, grouped by sequence (G45). "
            "Cover every requirement in the brief, check prerequisite order and the quarters "
            "each course is offered, keep to the student's standards and choose by their "
            "interests. Give each group a why of ONE short sentence here; a later step writes "
            "the full reasons. Use get_course when you are unsure, at most "
            f"{self.config.tool_calls_per_step} lookups in all; then call submit_plan."
        )
        fill = (
            "submit_plan",
            "Submit the whole plan as groups of courses with their quarters.",
            PlanSubmission,
        )
        try:
            sub = self._fill(system, f"{user}\n\n# Task\n\n{task}", fill, record)
        except AgentError as exc:
            logger.warning("%s: fill failed (%s): %s", TASK, exc.reason, _detail(exc))
            yield self.step(STEP_WRITE, "failed")
            error = ErrorEvent(message=UNAVAILABLE, reason="unavailable")
            yield from self._finish(run, error, status="failed")
            return
        yield self.step(STEP_WRITE, "done")
        groups = [
            Group(
                g.id, g.title, g.kind, g.why, list(g.rules), [(c.code, c.term) for c in g.courses]
            )
            for g in sub.groups
        ]

        yield self.step(STEP_CHECK, "started")
        valid, issues = self.check(self.state_of(groups), record)
        yield self.step(STEP_CHECK, "done")
        compromises: list[Compromise] = []
        valid, issues = yield from self._repair(
            system, user, groups, record, valid, issues, compromises
        )

        cited, seen = yield from self._explain(system, user, groups, record)
        summary = sub.notes.strip() or (
            f"{sum(len(g.placements) for g in groups)} courses in {len(groups)} groups."
        )
        yield PlanEvent(
            run_id=str(run.id),
            verdict="valid" if valid else "invalid",
            issues=issues,
            compromises=compromises,
            summary=summary,
        )
        yield from self._proposals(run, groups, cited, seen)
        yield from self._finish(
            run, None, status="ok" if valid else "invalid", profile_answers=self._answers(state)
        )

    def _fill(
        self,
        system: str,
        body: str,
        fill: tuple[str, str, type[PlanSubmission]],
        record: dict[str, Any],
    ) -> PlanSubmission:
        """The whole plan in one submit. Live (2026-11-26), Opus 5.5 checked course after course
        until the lookups ran out, which ended the run: then it is asked once more, with no
        tools, to submit what it has; the checker and the repair rounds catch the rest."""
        seconds = self.config.write_seconds
        spec = self.spec(
            system, body, fill, record, check=self._fill_check(), tokens=WRITE_TOKENS,
            seconds=seconds,
        )  # fmt: skip
        try:
            return self._kept(run_agent(self.llm, spec, sink=self.log.sink).output)
        except AgentError as exc:
            if exc.reason != "budget_tool_calls":
                raise
            logger.info("%s: lookups ran out; asking for the plan without tools", TASK)
        again = (
            f"{body}\n\nYou have used all your catalog lookups. Submit the whole plan now with "
            "what you know; Quarterly's checker will report any problem and you can repair it."
        )
        spec = self.spec(
            system, again, fill, record, check=self._fill_check(), tools=False,
            tokens=WRITE_TOKENS, seconds=seconds,
        )  # fmt: skip
        return self._kept(run_agent(self.llm, spec, sink=self.log.sink).output)

    def _repair(
        self,
        system: str,
        user: str,
        groups: list[Group],
        record: dict[str, Any],
        valid: bool,
        issues: list[PlanIssue],
        compromises: list[Compromise],
    ) -> Generator[BaseModel, None, tuple[bool, list[PlanIssue]]]:
        """Verify -> repair rounds, as in the prototype: stop when valid (after at most
        `max_polish_rounds` on fixable warnings), on thrash, or after `repair_rounds`."""
        history: list[str] = []
        last: frozenset[tuple[str, str, str]] | None = None
        repeats = rounds = polish = 0
        submit = ("submit_repair", "Submit this round's repair.", RepairSubmission)
        while rounds < self.config.repair_rounds:
            errors = [i for i in issues if i.level == "error"]
            codes = self.config.fix_warning_codes
            fixable = [i for i in issues if i.level == "warning" and i.code in codes]
            if valid and (not fixable or polish >= self.config.max_polish_rounds):
                break
            if not errors:
                polish += 1
            rounds += 1
            name = STEP_FIX.format(n=rounds)
            yield self.step(name, "started")
            task = (
                "Quarterly's verifier found problems. Repair the plan with the FEWEST changes "
                f"(at most {self.config.max_ops_per_round} add, move or remove operations). Bend "
                "the lowest tier first and list each rule you bend. If no errors are left, fix "
                "the listed warnings only when that adds no error; otherwise submit no "
                "operations. Do not undo an earlier round unless it caused a problem."
            )
            body = (
                f"{user}\n\n# Current plan (quarter: course (group))\n\n{self._grid(groups)}\n\n"
                f"# Verifier result (errors first)\n\n{self._issues_text(issues)}\n\n"
                f"# Earlier rounds\n\n{chr(10).join(history) or 'None.'}\n\n# Task\n\n{task}"
            )
            try:
                fix = run_agent(
                    self.llm,
                    self.spec(system, body, submit, record, check=self._repair_check()),
                    sink=self.log.sink,
                ).output
            except AgentError as exc:
                logger.warning("%s: repair failed (%s): %s", TASK, exc.reason, _detail(exc))
                yield self.step(name, "failed")
                break
            skipped = self._apply_repair(groups, fix)
            compromises += [
                Compromise(rule=b.rule, tier=b.tier, why=b.why, traded=b.traded) for b in fix.bent
            ]
            note = "; ".join(skipped)
            history.append(f"- round {rounds}: {fix.summary} ({len(fix.ops)} ops) {note}".rstrip())
            valid, issues = self.check(self.state_of(groups), record)
            yield self.step(name, "done")
            signature = frozenset(
                (i.code, ",".join(sorted(i.course_ids)), ",".join(sorted(i.term_ids)))
                for i in issues
                if i.level == "error"
            )
            repeats = repeats + 1 if signature == last else 1
            last = signature
            if errors and repeats >= self.config.thrash_same_errors:
                break
            if not errors and not fix.ops:
                break
        return valid, issues

    def _explain(
        self, system: str, user: str, groups: list[Group], record: dict[str, Any]
    ) -> Generator[BaseModel, None, tuple[dict[str, list[tuple[str, str, str]]], set[str]]]:
        yield self.step(STEP_EXPLAIN, "started")
        cited: dict[str, list[tuple[str, str, str]]] = {}
        seen = self.known_ids(record)
        task = (
            "The plan is final. The student will be walked through it one sequence at a time, "
            "with your text beside the highlighted courses. For each group, write one paragraph "
            "of four to six sentences (G46): first what the sequence is about (what its courses "
            "cover and how they build on each other), then why it suits this student (name an "
            "interest, goal or standard from the record or the working information) and why "
            "these quarters. Plain words, no lists. Cite the ids you used (profile:<field>, "
            "course:CODE, post:N, summary:N, guideline:Gnn). Call submit_explanations."
        )
        body = (
            f"{user}\n\n# Final plan (quarter: course (group))\n\n{self._grid(groups)}\n\n"
            f"# Task\n\n{task}"
        )
        submit = ("submit_explanations", "Submit one reason per group.", ExplanationsSubmission)
        try:
            written = run_agent(
                self.llm, self.spec(system, body, submit, record), sink=self.log.sink
            )
        except AgentError as exc:
            logger.warning("%s: explanations failed (%s): %s", TASK, exc.reason, _detail(exc))
            yield self.step(STEP_EXPLAIN, "failed")
            return cited, seen
        seen |= written.seen_ids
        by_id = {g.id: g for g in groups}
        for e in written.output.groups:
            if e.id in by_id and e.why.strip():
                by_id[e.id].why = e.why.strip()
                refs = (split_ref(c) for c in e.citations)
                cited[e.id] = [(kind, ident, "") for kind, ident in (r for r in refs if r)]
        yield self.step(STEP_EXPLAIN, "done")
        return cited, seen

    def _answers(self, state: RunState) -> dict[str, Any] | None:
        """A browser plan stores the answers of this run itself (`done.profile_answers`)."""
        if self.account is not None:
            return None
        qs = {q.field: q for q in question_set().questions}
        out = {
            a.field: coerce_answer(qs[a.field], state.answers[a.question_id])
            for a in state.asked
            if a.field and a.question_id in state.answers and a.field in qs
        }
        return {k: v for k, v in out.items() if v is not None} or None

    def _proposals(
        self,
        run: m.AgentRun,
        groups: list[Group],
        cited: dict[str, list[tuple[str, str, str]]],
        seen: set[str],
    ) -> Iterator[BaseModel]:
        rules = load_guideline().rules
        base = plan_hash(self.req.plan)

        def order(g: Group) -> tuple[int, tuple[int, int]]:
            first = min((term_key(t) for _, t in g.placements), default=(0, 0))
            return KIND_ORDER.get(g.kind, 9), first

        rows: list[tuple[Group, list[ChangeOp]]] = [
            (g, self._ops_for(g)) for g in sorted(groups, key=order)
        ]
        removal = self._removals(groups)
        if removal:
            rows.append((Group("replace", REPLACE_TITLE, "replace", REPLACE_WHY, [], []), removal))
        for g, ops in rows:
            if not ops:
                continue
            citations = checked_citations(TASK, cited.get(g.id, []), seen)
            refs = [RuleRef(id=r, text=rules[r].text) for r in g.rules if r in rules]
            change_set_id = None
            if self.saved is not None:
                row = plans_repo.store_change_set(
                    self.db,
                    self.saved,
                    origin="generate",
                    ops=ops,
                    base_plan_hash=base,
                    preview=None,
                )
                row.run_id = run.id
                row.meta = {
                    "group_id": g.id,
                    "title": g.title,
                    "kind": g.kind,
                    "why": g.why,
                    "citations": [_plain(c) for c in citations],
                    "rules": [_plain(r) for r in refs],
                }
                self.db.flush()
                change_set_id = str(row.id)
            yield PlannerProposalEvent.model_validate(
                {
                    "change_set_id": change_set_id,
                    "group_id": g.id,
                    "title": g.title,
                    "kind": g.kind,
                    "ops": ops,
                    "why": g.why,
                    "citations": citations,
                    "rules": refs,
                    "preview": self._verdict(ops),
                    "base_plan_hash": base,
                }
            )
