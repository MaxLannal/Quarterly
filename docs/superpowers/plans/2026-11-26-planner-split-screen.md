# Planner split screen and planner agent: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One planner page: the four-year plan on the left in four year-columns, the planner agent on the right. Opus 5.5 (through Teamorouter) writes a first plan from the student's General Information and interests, guided by `data/planner/plan-guideline.md`, shows each course or sequence as an unsaved proposal, walks the student through each sequence with a glowing outline, and fixes the plan in chat.

**Architecture:** A new package `services/api/api/agents/planner/` ports the degree-plan-agent harness (intake → ask → fill → verify → repair → explain) onto `llm_gateway` and `planner_core`, and absorbs the advisor chat. One SSE endpoint, `POST /agents/planner`, serves both modes. The web planner replaces `GenerateDialog` and `AdvisorSheet` with a `PlannerPanel` beside a column-per-year `PlanGrid`; proposals render as dashed blocks in their quarter cells.

**Tech stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic, `planner_core`, `llm_gateway` (FakeLLM in tests); React + TS, Tailwind v4, TanStack Query, dnd-kit, vitest, Playwright with MSW.

**Spec:** `docs/superpowers/specs/2026-11-26-planner-split-screen-design.md` (read it with this plan). Also the agent instructions of issues #18 and #17, and the prototype `ZhihchengGao/degree-plan-agent` (`src/qplan/harness.py`, `tools.py`, `principles/`).

## Global Constraints

- Model ids only in `llm_routing.yaml`. Teamorouter address only in `.env` (`ANTHROPIC_BASE_URL=https://api.teamorouter.com`), key only in `.env` (`ANTHROPIC_API_KEY`). Never print or commit the key.
- `packages/planner_core` imports no DB, web framework, HTTP or LLM client.
- A plan is "valid" only when `verify_checked` reports no errors and `check_certificate()` accepts the certificate. The model never says a plan is valid.
- Agents never write the plan or the record. They draft `change_set` rows (status `proposed`) or `profile_proposal` rows. Exception decided in the spec: `note_preference` appends to `student_profile.working_notes` (the agent's memory, visible and clearable).
- Never log emails or IPs; day-level dates only. No browser request leaves the site's origin.
- Tests use `FakeLLM`; `LLM_LIVE=false` in tests. Live calls only in Task 16 (Max approved about 5-10 plans, up to about $15).
- Catalog facts come only from the seed; every guideline rule that states a UChicago fact carries its source URL.
- Do not run Prettier. Follow surrounding style; eslint and tsc are the checks.
- `make api-client` after every API change; frontend types come only from the generated client.
- Accessibility: real buttons, 44 px targets, 4.5:1 contrast, visible focus, keyboard paths, `prefers-reduced-motion`.
- Copy: plain, short sentences (the project writes in ASD-STE100 style).
- Limits (from the spec): repair rounds 5, same-errors thrash stop 3, ops per repair round 12, model questions before planning 2, options per question 2-5 plus "Other", chat proposals per answer 3, generation 10/day per account and 3/day logged out, chat 60/day per account and 30/day logged out.

## Review Focus

1. **The student edits the grid while proposals are pending.** Expected: proposals whose ops still apply stay; one whose course was dragged in by hand turns stale with "This proposal no longer fits your plan" and **Ask again**. Tests: Task 8 `test_planner_change_set_goes_stale_when_course_added_by_hand`, Task 12 `stale proposal shows ask again`.
2. **Accepting a later group after rejecting its prerequisite group.** Expected: it applies; the plan check shows the missing-prerequisite error; nothing crashes. Tests: Task 8 `test_planner_change_sets_apply_out_of_order`, Task 10 `applies a later group after a rejected one`.
3. **The model submits a course code that does not exist or a quarter outside the plan.** Expected: the submit check rejects it with a message and the model gets its one repair turn; a second failure ends the run with an `error` event and no proposals. Test: Task 6 `test_fill_rejects_unknown_code_then_accepts_repair`.
4. **A paused run is answered after its state expired, or after a reload.** Expected: a reload shows the pending question again from the stored chat; an answer to an expired run gets `error {reason: "expired"}` and the panel offers **Start again**. Tests: Task 6 `test_resume_after_state_expired`, Task 12 `question survives reload`.
5. **The walkthrough lands on a course in a collapsed Summer.** Expected: that Summer row opens so the glow is visible, and closes again when the step moves on unless the student opened it. Test: Task 13 `opens a collapsed summer for its step`.

---

## File map

- Backend, new: `services/api/api/agents/planner/{__init__,guideline,brief,standards,state,harness,chat}.py`, `services/api/api/schemas/planner.py`, `services/api/api/routers/planner.py`, `services/api/api/migrations/versions/0012_planner_agent.py`, `data/planner/plan-guideline.md`, `data/planner/config.yaml`, `prompts/a1_planner.md`, `prompts/a1_planner_chat.md`, `scripts/planner_live.py`.
- Backend, changed: `packages/llm_gateway/llm_gateway/{providers,gateway}.py`, `services/api/api/{config,profile_data}.py`, `services/api/api/agents/{llm,runtime,e2e_llm,tools}.py`, `services/api/api/db/models.py`, `services/api/api/routers/{agents,plans,profile}.py`, `services/api/api/schemas/{agents,profile}.py`, `services/api/api/main.py`, `data/profile/questions.yaml`, `llm_routing.yaml`, `.env.example`.
- Backend, removed (end of Task 8): `services/api/api/agents/generate.py`, `services/api/api/agents/chat.py` (logic moved to `planner/chat.py`), `prompts/a1_preferences.md`, `a1_rationale.md`, `a2_chat.md`, their tests and evals entries; routes `/agents/generate`, `/agents/chat`, `/agents/chat/history`.
- Frontend, new: `apps/web/src/features/planner-agent/` with `PlannerPanel.tsx`, `ChatThread.tsx`, `QuestionCard.tsx`, `PlannerProposalCard.tsx`, `ProposalBlock.tsx`, `usePlannerRun.ts`, `useWalkthrough.ts`, `Walkthrough.tsx`, `proposals.ts`, `history.ts`, `HistoryPanel.tsx`, `DetailsPanel.tsx`, and tests.
- Frontend, changed: `apps/web/src/features/planner/{Planner,PlanGrid,CourseCard,localPlans,importOnLogin,context}.tsx|ts`, `apps/web/src/api/{sse,types}.ts`, `apps/web/src/mocks/agents.ts`, `apps/web/src/features/advisor/AdvisorPanel.tsx` (keeps `CitationChip`; `AdvisorSheet` removed), the global stylesheet (glow keyframes), `apps/web/e2e/{planner,agents}.spec.ts`, `apps/web/e2e-stack/journey-*.spec.ts`.
- Frontend, removed: `apps/web/src/features/generate/GenerateDialog.tsx` and its test; `features/generate/deterministic.ts` too if nothing else imports it.

---

### Task 1: Teamorouter base URL and the planner routes

**Files:** Modify `packages/llm_gateway/llm_gateway/providers.py`, `packages/llm_gateway/llm_gateway/gateway.py`, `services/api/api/config.py`, `services/api/api/agents/llm.py`, `llm_routing.yaml`, `.env.example`. Test: `packages/llm_gateway/tests/test_providers.py`, `packages/llm_gateway/tests/test_routing.py`.

**Interfaces — Produces:** `AnthropicBackend(api_key: str, client: Any | None = None, base_url: str | None = None)`; `build_gateway(*, anthropic_api_key, openrouter_api_key, anthropic_base_url: str | None = None, sink=..., routing=None)`; `Settings.anthropic_base_url: str = ""`; routing tasks `a1_planner_agent`, `a1_planner_chat`.

- [ ] **Step 1: failing tests.** `test_anthropic_backend_passes_base_url` (patch `anthropic.Anthropic`; assert called with `base_url="https://api.teamorouter.com"` and `max_retries=0`); `test_anthropic_backend_no_base_url_by_default` (no `base_url` kwarg, so the SDK's own env lookup still works); `test_routing_has_planner_tasks` (`route("a1_planner_agent")`: model `claude-opus-5-5`, effort `medium`, `max_tokens` 16000; `route("a1_planner_chat")`: model `claude-opus-5-5`, effort `low`, `max_tokens` 6000; both fall back to OpenRouter `anthropic/claude-opus-5.5`).
- [ ] **Step 2:** `uv run pytest packages/llm_gateway/tests -k "base_url or planner_tasks" -v` → FAIL.
- [ ] **Step 3: implement.** Pass `base_url` only when non-empty. `configure_llm` passes `settings.anthropic_base_url or None`. Route comment: "Max, 2026-11-26: Opus 5.5 for the planner agent (issue #17), through Teamorouter." `refusal_fallback: true` for now (Task 16 turns it off if Teamorouter rejects the beta). `.env.example`: a commented `ANTHROPIC_BASE_URL=` line explaining it is an optional Anthropic-compatible proxy.
- [ ] **Step 4:** rerun → PASS; `uv run mypy packages/llm_gateway --strict` clean.
- [ ] **Step 5: commit** `feat(llm): optional Anthropic base URL; Opus 5.5 planner routes`.

### Task 2: `plan-guideline.md`, `config.yaml` and their loader

**Files:** Create `data/planner/plan-guideline.md`, `data/planner/config.yaml`, `services/api/api/agents/planner/__init__.py`, `services/api/api/agents/planner/guideline.py`. Test: `services/api/tests/test_planner_guideline.py`.

**Interfaces — Produces:**
```python
Tier = Literal["hard", "strong", "preference", "tiebreak"]
@dataclass(frozen=True)
class Rule: id: str; tier: Tier; text: str; why: str; source: str | None
@dataclass(frozen=True)
class Guideline: text: str; rules: dict[str, Rule]   # text = the whole file, for the system prompt
class PlannerConfig(BaseModel):  # extra="forbid"
    questions_max: int = 2; min_options: int = 2; max_options: int = 5
    repair_rounds: int = 5; thrash_same_errors: int = 3; max_ops_per_round: int = 12
    fix_warning_codes: list[str] = ["V04", "V10", "V11"]; max_polish_rounds: int = 2
    tool_calls_per_step: int = 4; chat_proposals_max: int = 3
    working_info_chars: int = 4000; run_seconds: int = 300; state_ttl_days: int = 1
def load_guideline() -> Guideline          # lru_cached; data/planner/plan-guideline.md
def load_planner_config() -> PlannerConfig # data/planner/config.yaml
```
Rule lines have one fixed form the loader parses: `- **G07** · strong · <rule>`, then an indented `Why: ...` line and an optional indented `Source: <url>` line.

- [ ] **Step 1: failing tests.** `test_guideline_rules_parse` (at least 25 rules; ids `G01`… unique; tiers valid; every rule has a non-empty `why`); `test_guideline_sections_present` (the nine section headings of spec 6.1, in order); `test_guideline_cites_sources_for_facts` (every rule in "Offerings and sequences" and "CS major facts" has a `source` starting `https://`); `test_planner_config_loads` (the values above; an unknown key raises).
- [ ] **Step 2:** `uv run pytest services/api/tests/test_planner_guideline.py -v` → FAIL.
- [ ] **Step 3: write the guideline**, nine sections as in spec 6.1. Port P01-P17 from the prototype's `principles.yaml` and every line of `planning_facts.md` with their source URLs. Add the new sections: student standards; interests (first among preferences, each choice names the interest it serves, forum evidence breaks ties); explaining choices (group by sequence, 2-3 sentences, must name a record or working-information fact, cite `course:` / `post:` / `summary:` / `profile:<field>` / `guideline:Gnn`, never generic); changing the plan in chat (only what was asked, keep locked items, one change set per course or sequence, re-check prerequisites and offerings of everything that moves, `note_preference`, say the cost). Then `guideline.py`.
- [ ] **Step 4:** rerun → PASS.
- [ ] **Step 5: commit** `feat(planner): plan-guideline.md and planner config`.

### Task 3: Interests question, migration 0012 and `student.md`

**Files:** Modify `data/profile/questions.yaml`, `services/api/api/db/models.py`, `services/api/api/profile_data.py`, `services/api/api/schemas/profile.py`; create `services/api/api/migrations/versions/0012_planner_agent.py`. Test: `services/api/tests/test_migrations.py`, `test_profile_data.py`, `test_profile_questions.py` (use the existing test files that cover these modules).

**Interfaces — Produces:** `StudentProfile.interests: Mapped[list[str] | None]` (JSONB); `AgentRun.state: Mapped[dict[str, Any] | None]` (JSONB); `ChangeSet.run_id: Mapped[uuid.UUID | None]` (FK `agent_run.id`, `ondelete="SET NULL"`); `ChangeSet.meta: Mapped[dict[str, Any] | None]` (JSONB: `group_id, title, kind, why, citations, rules`); new `ProfileProposal(id, account_id FK account ondelete CASCADE, field String(48), value JSONB, source String(24) default "planner_chat", status String(16) default "proposed", created_day)`; `"interests"` in `LIST_FIELDS`; profile out and patch schemas gain `interests: list[str] | None`.

- [ ] **Step 1: failing tests.** `test_0012_upgrade_downgrade_upgrade`; the existing `test_models_match_migration` covers the new columns; `test_questions_have_interests` (`id == field == "interests"`, group `goals`, type `list`, step 2, no `when`); `test_student_md_lists_interests` (`["machine learning", "philosophy of mind"]` renders `- Interests: machine learning; philosophy of mind` under `## Goals`; empty renders `- Interests: Not answered`); `test_patch_profile_sets_interests`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement.** Question text "Which subjects or topics interest you most?", label "Interests", help "Add as many as you like, for example machine learning, philosophy of mind or Chinese.", `options: []`. `down_revision` = the revision id inside `0011_course_load.py`.
- [ ] **Step 4:** rerun → PASS (migration tests use the test database, not the shared stack).
- [ ] **Step 5: commit** `feat(record): interests question; migration 0012 for the planner agent`.

### Task 4: Planner event contract and citations

**Files:** Create `services/api/api/schemas/planner.py`; modify `services/api/api/schemas/agents.py` (Citation kinds, `ErrorEvent.reason`, `DoneEvent`), `services/api/api/agents/runtime.py` (`checked_citations`, `citation_label`), `docs/CONTRACTS.md`. Test: `services/api/tests/test_planner_schemas.py`, the existing runtime test file.

**Interfaces — Produces (Pydantic, `extra="forbid"`):**
```python
class QuestionAnswer(BaseModel): question_id: str; option: str | None = None; text: str | None = None
class PendingProposal(BaseModel): group_id: str; ops: list[ChangeOp]; base_plan_hash: str
class PlannerRequest(BaseModel):
    mode: Literal["generate", "chat"]; plan: PlanState; plan_id: uuid.UUID | None = None
    message: str | None = None                    # chat
    run_id: uuid.UUID | None = None               # resume a paused generate run
    answer: QuestionAnswer | None = None          # with run_id
    history: list[ChatTurn] = []                  # local plans: last 12 turns
    pending: list[PendingProposal] = []           # local plans: open proposals ("apply it")
    profile_answers: dict[str, Any] = {}          # local plans: General Information answers
    working_notes: str | None = None              # local plans
    today_term: str | None = None
class QuestionEvent(BaseModel): type: Literal["question"] = "question"; run_id: str; question_id: str; field: str | None; text: str; options: list[str]; allow_other: bool = True
class Compromise(BaseModel): rule: str; tier: str; why: str; traded: str
class PlanEvent(BaseModel): type: Literal["plan"] = "plan"; run_id: str; verdict: Literal["valid", "invalid"]; issues: list[Issue]; compromises: list[Compromise]; summary: str
GroupKind = Literal["major", "core", "elective", "minor", "replace", "other"]
class RuleRef(BaseModel): id: str; text: str   # the guideline rule a group follows, with its text for the chip
class PlannerProposalEvent(BaseModel): type: Literal["proposal"] = "proposal"; change_set_id: str | None; group_id: str; title: str; kind: GroupKind; ops: list[ChangeOp]; why: str; citations: list[Citation]; rules: list[RuleRef]; preview: Verdict
PlannerEvent = Annotated[StepEvent | QuestionEvent | PlanEvent | PlannerProposalEvent | MessageEvent | ConfirmEvent | DoneEvent | ErrorEvent, Field(discriminator="type")]
```
`Verdict` is the existing preview verdict shape (`valid`, error and warning counts) from `ToolBox._verdict`. `ErrorEvent.reason` gains `"expired"`. `DoneEvent` gains `working_notes: str | None = None` (local plans only). `Citation.kind` gains `"profile"` and `"guideline"`. `checked_citations(..., profile_fields: set[str] = frozenset(), guideline_ids: set[str] = frozenset())` keeps `profile:<field>` only for a non-empty field of this student and `guideline:<id>` only for an existing rule id. `citation_label("profile", "interests") == "Your interests"`; `citation_label("guideline", "G07") == "Guideline G07"`.

- [ ] **Step 1: failing tests.** `test_planner_event_round_trip` (each event type dumps and validates through `TypeAdapter(PlannerEvent)`); `test_checked_citations_profile_and_guideline` (drops `profile:pace` when pace is empty, keeps `profile:interests` when set, drops `guideline:G99`, keeps `guideline:G07`).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement.** Write the "Planner agent (issue #17)" section of `docs/CONTRACTS.md` (endpoint rows from Task 8, these events, resume and re-base rules). Run `make api-client`.
- [ ] **Step 4:** rerun → PASS; `npm --prefix apps/web run typecheck` passes.
- [ ] **Step 5: commit** `feat(planner): event contract`.

### Task 5: Requirements brief and standards checks

**Files:** Create `services/api/api/agents/planner/brief.py`, `services/api/api/agents/planner/standards.py`. Test: `services/api/tests/test_planner_brief.py`, `services/api/tests/test_planner_standards.py`.

**Interfaces — Produces:**
```python
def requirements_brief(state: PlanState, rules: RuleSet, catalog: Catalog, report: Report, *, max_candidates: int = 40) -> str
def known_codes(state: PlanState, catalog: Catalog) -> set[str]
@dataclass(frozen=True)
class Standards: away_terms: frozenset[str]; max_units: int | None; avoid: frozenset[str]
def standards_from(record: dict[str, Any], working_notes: str | None) -> Standards   # record = General Information answers (saved record or local answers)
def standard_issues(state: PlanState, catalog: Catalog, standards: Standards) -> list[Issue]  # level "error"; codes S01 away, S02 load, S03 avoid
def preference_line(day: dt.date, kind: str, text: str, courses: list[str]) -> str            # "- 2026-11-26 · avoid · <text> [CMSC 12345, ...]"
```
`avoid` = the course codes on working-information lines of kind `avoid`. `max_units` from `course_load` using the College's units in `college_policy.yaml`.

- [ ] **Step 1: failing tests.** `test_brief_lists_unmet_nodes_with_offered_quarters` (CS BS first-year: names the intro sequence node, lists `CMSC 14100` with its usual quarter from the seed, never lists a `credit_only` course such as `TRNC 10100`); `test_brief_skips_met_nodes` (a credit that meets calculus removes that node); `test_standard_issues_away_load_avoid` (away quarter → `S01`; over `max_units` → `S02`; avoided course → `S03`); `test_preference_line_round_trips` (`standards_from` reads back the codes `preference_line` wrote).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement.** Port `PlanTools.requirements_brief` and `_candidates` from the prototype's `tools.py`, using `planner_core.index.Index` and the offering probabilities `planner_core` already uses.
- [ ] **Step 4:** rerun → PASS.
- [ ] **Step 5: commit** `feat(planner): requirements brief and student standards`.

### Task 6: The harness, generate mode

**Files:** Create `services/api/api/agents/planner/state.py`, `services/api/api/agents/planner/harness.py`, `prompts/a1_planner.md`. Test: `services/api/tests/test_planner_harness.py`.

**Interfaces — Consumes:** Tasks 2, 4, 5; `ToolBox` (`agents/tools.py`) for read tools; `run_agent(llm, AgentSpec)`; `verify_checked`, `apply_ops`, `check_certificate`; `render_student_md()`; `RunLog`, `new_run`.
**Produces:**
```python
class AskedQuestion(BaseModel): question_id: str; field: str | None; text: str; options: list[str]
class RunState(BaseModel):  # agent_run.state
    phase: Literal["ask", "fill"]; asked: list[AskedQuestion]; answers: dict[str, QuestionAnswer]; day: dt.date
class GroupCourse(BaseModel): code: str; term: str
class Group(BaseModel): id: str; title: str; kind: GroupKind; courses: list[GroupCourse]; why: str; rules: list[str]
@dataclass
class PlannerRun:
    db: Session; llm: object; req: PlannerRequest; account: m.Account | None; saved: m.Plan | None
    show_unpublished: bool; statuses: tuple[str, ...]; log: RunLog
    def generate_events(self) -> Iterator[BaseModel]
```
Step names streamed, in order: "Reading your information", "Checking what can fit", "Writing your plan", "Checking the plan", "Fixing the plan (round n)", "Explaining each choice". Fill: submit tool `submit_plan {groups: [{id, title, kind, courses: [{code, term}], why, rules}], notes}`; its `check` raises `ValueError` naming each unknown code, each term outside the plan's terms, and each course in two groups. Repair: `submit_repair` (prototype schema, plus `group_id` on each op). Explain: `submit_explanations {groups: [{id, why, citations: [str]}]}`; a group whose course set changed keeps its fill `why`. Groups become ops relative to the request plan: `add` for new placements, `move` when an unlocked existing item of that course is in another term; one more group, kind `replace`, title "Courses this plan replaces", holds `remove` ops for unlocked existing items the plan dropped. Saved plan: each group is a `change_set` (`origin="agent"`, `run_id`, `meta`). Before a question: save `RunState`, emit `QuestionEvent`, then `DoneEvent`, and stop. Required-field questions (`intended_programs`, `interests`, `expected_graduation_term`) come from `data/profile/questions.yaml` without a model call; the model may then ask up to `questions_max` more.

- [ ] **Step 1: failing tests (FakeLLM scripts).** `test_generate_cs_student_valid_plan` (first-year CS BS, `interests=["machine learning"]`; scripted `submit_plan` passes verify; events `step… plan(verdict="valid") proposal×N done`; one proposal per group; each `why` non-empty; a `profile:interests` citation survives); `test_generate_asks_interests_when_empty` (no interests → a `QuestionEvent(field="interests")`; `agent_run.state["phase"] == "ask"`; no model call); `test_resume_with_answer_continues` (request with `run_id` and the answer → plan returned; a `profile_proposal` row for `interests` with status `proposed`); `test_resume_after_state_expired` (state day older than `state_ttl_days` → `ErrorEvent(reason="expired")`); `test_fill_rejects_unknown_code_then_accepts_repair`; `test_repair_round_fixes_prereq_error` (`CMSC 14200` before `CMSC 14100`; the repair move makes it valid); `test_repair_stops_on_thrash` (same errors three rounds → `PlanEvent(verdict="invalid")` with issues; proposals still sent); `test_standard_issues_go_to_repair` (a course in an away quarter gets repaired); `test_regenerate_proposes_removals_and_keeps_completed`; `test_model_never_sets_verdict` (the verdict comes only from `verify_checked` and the certificate).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement**, porting the prototype's `intake`, `interview`, `fill`, `verify`, `repair_loop` and `_update_why`, with `shape` folded into fill (one strategy). System prompt = `prompts/a1_planner.md` + `load_guideline().text` + the brief. User message = `student.md` + the working information (all of it, or the lines that share a word with the student's programs and interests when over `working_info_chars`) + the feasibility line + the standards. Budgets from `PlannerConfig`.
- [ ] **Step 4:** rerun → PASS.
- [ ] **Step 5: commit** `feat(planner): generate mode of the planner agent`.

### Task 7: The harness, chat mode

**Files:** Create `services/api/api/agents/planner/chat.py`, `prompts/a1_planner_chat.md`; move the reusable parts of `services/api/api/agents/chat.py` (`chat_run`, `history`, the scope gate, `confirmation_problem`) into it; modify `services/api/api/agents/tools.py` (proposal metadata; the proposal limit from config). Test: `services/api/tests/test_planner_chat.py` (port the still-relevant cases of the old chat tests).

**Interfaces — Produces:** `PlannerRun.chat_events(self) -> Iterator[BaseModel]`. Tools: `note_preference {text, kind: "avoid"|"prefer"|"schedule"|"other", courses: [str]}` appends `preference_line(...)` to the working information (saved: `student_profile.working_notes`; local: returned in `DoneEvent.working_notes`); `propose_change_set {ops, group_id, title, kind, why, citations, rules}` (at most `chat_proposals_max`, refuses an op that adds an avoided course, with an error the model sees); `submit_answer {text, citations}`. `purge_old_history(db)` deletes only messages whose plan no longer exists; `clear_history(db, plan) -> int`.

- [ ] **Step 1: failing tests.** `test_chat_proposes_one_change_set_per_sequence` ("I hate Language and the Human, suggest a new Core" → one `proposal`, kind `core`, ops replace that sequence, `why` cites `profile:` or `post:`); `test_chat_note_preference_appends_dated_line` (saved: the record's `working_notes` ends with the new line; local: `DoneEvent.working_notes` has it); `test_chat_avoid_list_blocks_proposal`; `test_chat_explains_without_proposal` ("Why CMSC 27100 in Autumn of year 2?" → `MessageEvent` with a `guideline:` or `course:` citation, no proposal); `test_history_kept_while_plan_exists` (a 60-day-old message stays; deleting the plan removes it); `test_clear_history`; `test_typed_confirmation_still_works`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement.** System = `prompts/a1_planner_chat.md` + the guideline. Each turn gets `student.md`, the working information (all, or related lines), and the plan.
- [ ] **Step 4:** rerun → PASS.
- [ ] **Step 5: commit** `feat(planner): chat mode, working information, kept history`.

### Task 8: Endpoints, re-base on apply, profile proposals; remove the old agents

**Files:** Create `services/api/api/routers/planner.py`; modify `services/api/api/routers/plans.py` (apply), `services/api/api/routers/profile.py` (proposals), `services/api/api/main.py`, `services/api/api/agents/e2e_llm.py` (scripts for `a1_planner_agent` and `a1_planner_chat`); delete the old generate and chat modules, the routes `/agents/generate`, `/agents/chat`, `/agents/chat/history`, their prompts, tests and eval entries; remove `a1_plan_generator*` and `a2_advisor_chat*` from `llm_routing.yaml` (keep `a2_scope_classifier`). Test: `services/api/tests/test_planner_api.py`, plus the existing plans and profile API test files.

**Interfaces — Produces:** `POST /agents/planner` (SSE of `PlannerEvent`); `GET /agents/planner/history?plan_id` → `ChatHistory` (proposal entries carry their meta); `DELETE /agents/planner/history?plan_id` → 204; `GET /me/profile/proposals` → `list[ProfileProposalOut]`; `POST /me/profile/proposals` (`{field, value}`, only fields of the question file, for the import on login) → `ProfileProposalOut`; `POST /me/profile/proposals/{id}/accept` → `ProfileOut`; `POST /me/profile/proposals/{id}/reject` → 204. Rate limits: `mode="generate"` without `run_id` counts as a generation (10 / 3); a resume does not; `mode="chat"` counts as a chat message (60 / 30). Apply endpoint: for a change set with `run_id` set, a hash mismatch re-bases: if `apply_ops(current, ops)` succeeds, apply; otherwise mark `stale` and return 409 with detail "This proposal no longer fits your plan."

- [ ] **Step 1: failing tests.** `test_planner_generate_streams_events` (FakeLLM; `text/event-stream`; the last event is `done`); `test_planner_resume_not_rate_limited` (3 logged-out generations, then a resume still works, a 4th new generation is 429); `test_planner_change_sets_apply_out_of_order` (apply group 3, then group 1: both 200); `test_planner_change_set_goes_stale_when_course_added_by_hand` (PATCH adds the same course → apply 409, status `stale`); `test_strict_hash_kept_for_typed_confirmation`; `test_profile_proposal_accept_writes_field`; `test_profile_proposal_reject`; `test_profile_proposal_create_rejects_unknown_field`; `test_old_agent_routes_gone` (`/agents/generate`, `/agents/chat` → 404); `test_other_account_plan_is_404`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: implement**, then `make api-client`.
- [ ] **Step 4:** `uv run pytest services/api -q` → PASS; ruff and mypy clean.
- [ ] **Step 5: commit** `feat(planner): /agents/planner, re-based proposals, profile proposals; remove A1/A2`.

### Task 9: Web stream client and mocks

**Files:** Modify `apps/web/src/api/sse.ts`, `apps/web/src/api/types.ts`, `apps/web/src/mocks/agents.ts`. Test: `apps/web/src/api/sse.test.ts`.

**Interfaces — Produces:** `streamPlanner(body: S["PlannerRequest"], signal?: AbortSignal): AsyncGenerator<PlannerEvent>`; `type PlannerEvent = S["PlannerEvent"]` and `type GroupKind` in `api/types.ts`; mock `plannerReply(req): PlannerEvent[]`, a fixed CS run: with empty `profile_answers.interests`, a `question` for `interests`; otherwise steps, a valid `plan`, and six groups (Intro CS sequence CMSC 14100-14400, Calculus MATH 15100-15300, a Humanities sequence, SOSC, Theory CMSC 27100-27200, machine-learning electives) whose `why` names "machine learning"; a chat message that mentions "Language and the Human" returns one `core` proposal. Remove `streamGenerate`, `streamChat`, `generateVariants`, `chatReply`.

- [ ] **Step 1:** test `streamPlanner parses question, plan and proposal events`.
- [ ] **Step 2:** `npm --prefix apps/web run test -- sse` → FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** PASS; `npm --prefix apps/web run typecheck`.
- [ ] **Step 5: commit** `feat(web): planner stream client and mock run`.

### Task 10: Local plan storage, proposals and history logic

**Files:** Modify `apps/web/src/features/planner/localPlans.ts`, `apps/web/src/features/planner/importOnLogin.ts`; create `apps/web/src/features/planner-agent/proposals.ts`, `apps/web/src/features/planner-agent/history.ts`. Tests next to each.

**Interfaces — Produces:**
```ts
// LocalPlan gains:
chat?: ChatEntry[]; proposals?: Proposal[]; history?: HistoryEntry[]; workingNotes?: string; profileAnswers?: Record<string, unknown>;
// proposals.ts
export interface Proposal { id: string; changeSetId: string | null; groupId: string; title: string; kind: GroupKind; ops: ChangeOp[]; why: string; citations: Citation[]; rules: RuleRef[]; status: "proposed" | "stale"; runId: string }
export interface ProposedBlock { proposalId: string; course: string; action: "add" | "move-in" | "remove"; itemId?: string }
export function fromEvent(e: PlannerProposalEvent, runId: string): Proposal
export function proposedBlocks(plan: PlanState, proposals: readonly Proposal[]): Map<string, ProposedBlock[]>  // key = term
export function stillFits(plan: PlanState, p: Proposal): boolean   // applyOps does not throw
export function withLocks(plan: PlanState, ops: readonly ChangeOp[]): ChangeOp[]  // appends lock ops for the items the ops place (issue #18 step 13)
// history.ts
export interface HistoryEntry { id: string; day: string; label: string; ops: ChangeOp[]; inverse: ChangeOp[] }
export function inverseOps(before: PlanState, after: PlanState): ChangeOp[]
export function historyKey(planKey: string): string   // "quarterly.history.v1:<planKey>"
```
`ChatEntry` is the stored panel thread: `{role: "user" | "assistant" | "step" | "question" | "proposal" | "plan", ...}` with the event payload.

- [ ] **Step 1: failing tests.** `inverseOps undoes add, move and remove` (apply ops, then the inverse, gives the original items by course and term); `proposedBlocks marks adds, moves and removes per term`; `stillFits is false when the course is already in the plan`; `applies a later group after a rejected one`; `withLocks locks the placed items`; `local plan keeps chat, proposals and history across save and load`; `import on login copies working notes into an empty record and sends answers as proposals` (MSW: `PATCH /me/profile` gets `working_notes` only when the record has none; each answer for an empty field is a `POST /me/profile/proposals`).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: commit** `feat(web): local planner state, proposals and history`.

### Task 11: Four year-columns, compact cards and proposal blocks

**Files:** Modify `apps/web/src/features/planner/PlanGrid.tsx`, `apps/web/src/features/planner/CourseCard.tsx`, `apps/web/src/features/planner/context.tsx`, the global stylesheet; create `apps/web/src/features/planner-agent/ProposalBlock.tsx`. Test: `PlanGrid.test.tsx`, `ProposalBlock.test.tsx`.

**Interfaces — Consumes:** `proposedBlocks()` (Task 10). **Produces:** `PlannerContextValue` gains `proposals: Map<string, ProposedBlock[]>`, `glow: Set<string>` (proposal ids lit by the walkthrough), `selectProposal(id: string): void`, `openDetails(code: string): void`, `openSummers: Set<number>` with `setSummerOpen(year: number, open: boolean)`. CSS class `glow-ring`: an animated ring in the primary color; under `prefers-reduced-motion: reduce`, a static ring.

Layout: from `lg`, `grid-cols-4`, one `section` per year (`data-testid="year-N"`); a fifth year adds a column and the grid scrolls sideways (`overflow-x-auto`, columns `min-w-[200px]`); below `md`, one column (years stacked). Each column stacks Summer, Autumn, Winter, Spring; Summer is a 44 px "+ Summer" button unless it has items or proposals, Show Summer is on, or the walkthrough opened it. Compact card: code (semibold, tabular), short title (one line, `truncate`), units, requirement stripe; hours and difficulty in `title` and the details panel.

- [ ] **Step 1: failing tests.** `renders one column per year with four quarter slots`; `summer row is collapsed until it has a course`; `proposal blocks are dashed with a Proposed tag and the group title as accessible name`; `remove proposals strike through the existing card`; `clicking a proposal block selects its proposal`; `glow class only on blocks of the lit proposal`; the existing drag-and-drop test still passes.
- [ ] **Step 2:** `npm --prefix apps/web run test -- PlanGrid ProposalBlock` → FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** PASS; update `Planner.test.tsx` where it relied on year rows.
- [ ] **Step 5: commit** `feat(web): four year-columns and proposal blocks`.

### Task 12: The planner panel and the split layout

**Files:** Create `apps/web/src/features/planner-agent/{PlannerPanel,ChatThread,QuestionCard,PlannerProposalCard}.tsx`, `usePlannerRun.ts`; modify `apps/web/src/features/planner/Planner.tsx`, `apps/web/src/features/advisor/AdvisorPanel.tsx` (keep `CitationChip`; `profile` links to `/me#field-<field>`, `guideline` shows the rule text carried in `PlannerProposalEvent.rules`); delete `GenerateDialog.tsx`, `AdvisorSheet` and their tests. Test: `PlannerPanel.test.tsx`, `Planner.test.tsx`.

**Interfaces — Produces:** `usePlannerRun({plan, planId, local}) → { entries: ChatEntry[]; running: boolean; generate(): void; send(text: string): void; answer(a: QuestionAnswer): void; clear(): Promise<void>; proposals: Proposal[]; accept(id: string): Promise<boolean>; reject(id: string): Promise<void>; acceptAll(): Promise<void>; rejectAll(): Promise<void> }`. Saved plan: accept = `POST /plans/{id}/changesets/{cs}/apply`, reject = `.../discard`, 409 → `stale`. Local plan: `applyOps(withLocks(...))` plus a history entry; reject drops the proposal. Panel open state in `localStorage` key `quarterly.plannerPanel.v1`.

Behaviour: hidden by default; **Generate plan** and **Ask Quarterly** open it and move focus into it; Escape hides it and returns focus to the opener; from `lg` it is the right third (`lg:w-1/3`, grid `flex-1`), below that `components/ui/sheet.tsx` full screen; a "Generative AI" label; step lines; `QuestionCard` with option buttons and an "Other" text box; `PlannerProposalCard` with title, courses with quarters, why, chips, rules, Accept / Reject, and for stale ones "This proposal no longer fits your plan" with **Ask again**; **Accept all** / **Reject all** after a generation; **Clear chat** behind a confirm dialog; each new proposal announced in an `aria-live="polite"` region.

- [ ] **Step 1: failing tests.** `panel is hidden until Generate plan`; `focus moves into the panel and Escape hides it`; `question shows options and Other`; `question survives reload`; `accept applies the ops and locks the items`; `reject removes the blocks`; `stale proposal shows ask again`; `accept all applies every group`; `clear chat empties the thread after confirm`; `new proposals are announced`; `panel reopens after reload while proposals are pending`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** PASS; `npm --prefix apps/web run lint && npm --prefix apps/web run typecheck`.
- [ ] **Step 5: commit** `feat(web): planner panel beside the grid; remove the Generate popup and advisor sheet`.

### Task 13: The walkthrough

**Files:** Create `apps/web/src/features/planner-agent/useWalkthrough.ts`, `Walkthrough.tsx`. Test: `Walkthrough.test.tsx`.

**Interfaces — Produces:** `useWalkthrough(proposals: Proposal[]) → { step: number | null; total: number; current: Proposal | null; start(): void; next(): void; back(): void; stop(): void }`. Order: kind `major`, `core`, `minor`, `elective`, `other`, `replace`; within a kind, by earliest term. It sets `glow` (Task 11) to the current proposal, opens a collapsed Summer that holds one of its blocks, and scrolls its first block into view (`block: "nearest"`, `behavior: "auto"` under reduced motion, else `"smooth"`).

Behaviour: starts on its own when a generation's `done` arrives with proposals; "Step n of N", the proposal content, Accept / Reject (each advances), Back / Next / Skip tour; the last step says "That's the whole plan" with **Accept all**; a **Walk me through it** button on the plan card replays it. Buttons only, no hidden shortcuts; focus stays on the walkthrough card.

- [ ] **Step 1: failing tests.** `starts after a generation and lights the first major group`; `next and back move the glow`; `accept advances to the next group`; `skip clears the glow`; `opens a collapsed summer for its step`; `reduced motion uses the static ring`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: commit** `feat(web): guided walkthrough of the generated plan`.

### Task 14: Course details panel and edit history

**Files:** Create `apps/web/src/features/planner-agent/DetailsPanel.tsx`, `HistoryPanel.tsx`; modify `Planner.tsx` (a History button in the toolbar; below `lg` the details replace the agent panel). Test: `DetailsPanel.test.tsx`, `HistoryPanel.test.tsx`.

**Interfaces — Consumes:** `CourseOverview` (`features/courses/CourseOverview.tsx`), `RatingLine`, `history.ts`. Every edit path (drag, card menu, accept, revert) pushes a `HistoryEntry` built with `inverseOps(before, after)`; saved plans keep history in `localStorage` under `historyKey(remoteId)`, local plans in the `LocalPlan`.

- [ ] **Step 1: failing tests.** `clicking a course card opens its details with ratings`; `details replace the agent panel on a narrow screen and Back returns`; `history lists edits newest first`; `revert applies the inverse and adds its own entry`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: commit** `feat(web): course details panel and edit history with revert`.

### Task 15: Browser tests and journeys

**Files:** Modify `apps/web/e2e/planner.spec.ts`, `apps/web/e2e/agents.spec.ts`, the `apps/web/e2e-stack/journey-*.spec.ts` files that use Generate or the advisor, and `services/api/api/agents/e2e_llm.py` if the journeys need more scripted turns.

- [ ] **Step 1:** mock-data specs: Generate → interests question → answer → walkthrough over six groups → Accept all → plan check badge; chat "I hate Language and the Human" → one Core proposal → Accept; Clear chat; a keyboard path (Tab to Generate, Enter, Tab through Accept/Reject, Escape).
- [ ] **Step 2:** `E2E_PORT=4175 npm --prefix apps/web run e2e` → fix until PASS.
- [ ] **Step 3:** journeys on the panel; `make e2e` (it switches the stack to fake AI and builds images: no frontend edits meanwhile), then `make up`. See Task 17 about the shared stack.
- [ ] **Step 4: commit** `test(e2e): planner panel, walkthrough and chat`.

### Task 16: Live smoke and tuning on Teamorouter (paid, approved by Max)

**Files:** Create `scripts/planner_live.py`; modify `llm_routing.yaml` only if Teamorouter rejects a request field; tune `data/planner/plan-guideline.md` and the two prompts; append to `docs/LIVE-TEST-REPORT.md`.

`scripts/planner_live.py --student cs-first-year|cs-first-year-theory|cs-transfer --chat "<message>" --confirm-spend` builds a `PlannerRequest` from a fixture student (invented, no real person's data), runs `PlannerRun` with the real gateway against a test database, prints the events, the cost (`RunLog.cost`) and the seconds, and refuses to run without `--confirm-spend` and `LLM_LIVE=true`.

- [ ] **Step 1:** one smoke run (`cs-first-year`). If a field is rejected, turn it off in the route (`refusal_fallback: false` first) and say why in a YAML comment.
- [ ] **Step 2:** up to 6 more generations across the three fixtures; read each plan against the guideline; tune the guideline and prompts where a plan breaks a rule or an explanation is generic.
- [ ] **Step 3:** two chat turns: "I hate Language and the Human. Suggest a new Core." and "Make Autumn of my second year lighter."
- [ ] **Step 4:** record runs, verdicts, seconds and cost in `docs/LIVE-TEST-REPORT.md`; stop at $15 total.
- [ ] **Step 5: commit** `chore(planner): live smoke on Teamorouter; guideline tuning`.

### Task 17: Docs, full checks and review

**Files:** `docs/SPEC.md` (Planner, A1 and A2 become the planner agent, General Information), `docs/SPEC-CHANGES.md` (one row), `docs/DESIGN.md` ("Changes approved in FEEDBACK": split screen, year columns, glow), `docs/PROGRESS.md`, `docs/OPEN_QUESTIONS.md` (the new defaults, e.g. a saved plan's history kept on the device), `docs/FEEDBACK.md` if an item applies.

- [ ] **Step 1:** write the docs.
- [ ] **Step 2:** `make check` → all green. Shared stack: two other Compose projects run on this machine (`quarterly` from the main checkout, `quarterly-e2e` from another worktree). Before `make e2e`, `make migrate` or `make up`, confirm with Max which stack this worktree may replace.
- [ ] **Step 3:** the `spec-reviewer` subagent reviews the diff against `docs/SPEC.md`, the design and issues #17/#18; fix correctness gaps only.
- [ ] **Step 4: commit** `docs: planner split screen and planner agent`.
