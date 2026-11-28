# Planner page: split screen with the planner agent (design)

- Date: 2026-11-26
- Issues: #18 (the page), #17 (the planner agent it needs), #5 (plan quality: the guideline), #14 (interests question that was missed)
- Asked by: Max (human builder on these issues)
- Status: draft, waiting for Max's approval

## 1. Intent

Today the planner has a Generate popup (solver + Sonnet, issue #5 calls its plans "garbage") and a separate advisor sheet. Students cannot see why a course was chosen, and nothing tells the agent how a person plans.

We want one planner page. The plan is on the left and the planner agent on the right. The agent writes a first plan from the student's General Information and interests, guided by `plan-guideline.md`, and shows each proposed course as an unsaved block. A guided walkthrough then lights up each sequence in turn and explains, in the chat, why it fits this student. In the same chat, the student gives working information ("I hate Language and the Human", "lighter Autumn of year 2") and the agent fixes specific courses or recommends new ones, again as proposals the student accepts or rejects.

Success: a CS student opens `/plan`, clicks **Generate plan**, watches progress in the panel, gets a verified plan whose electives visibly follow their interests, is walked through each sequence with a reason that names their interests, and can change any part by chatting.

## 2. Decisions made by Max (2026-11-26)

| Id | Question | Answer |
|---|---|---|
| Approach | How the first plan is built | Port the degree-plan-agent prototype: Opus 5.5 writes the plan, the verifier checks it, Opus repairs it (max 5 rounds). |
| #18 D1 | Unsaved blocks when the panel closes or the page is left | They stay on the grid as proposals until accepted or rejected, also after a reload. |
| #17 D1 | How long the planner chat is kept | As long as the plan exists. The panel has **Clear chat**. |
| #17 D2 | Logged-out students | Yes. Answers and working information live in the local plan. `importOnLogin.ts` copies them to the student record. |
| Live calls | Paid Opus 5.5 calls while building | Yes, about 5-10 test plans, up to about $15 total, on the Teamorouter key. |

## 3. Goals, non-goals, anti-goals

**Goals**
1. `data/planner/plan-guideline.md`: the restrictions and preferences for planning, loaded into the agent's system prompt every run.
2. A planner agent (`POST /agents/planner`) that (a) generates one initial plan and (b) chats to fix courses and recommend new ones, on Opus 5.5 through Teamorouter.
3. Tuned and tested on the Computer Science major first (`cmsc-ba`, `cmsc-bs`). Other programs go through the same agent but are not tuned in this round.
4. The split-screen planner page with a four-column grid (one column per year).
5. Proposals as unsaved blocks, Accept/Reject per course or sequence, and an edit history with Revert.
6. The guided walkthrough: one glowing sequence at a time, its explanation in the panel.
7. A course-details panel when the student clicks a block.

**Non-goals (this round)**
- Tuning for majors other than CS. The audit of fixed sequences in every program (#3).
- Two alternative plans. The prototype builds two; we build one.
- Questions in the middle of filling or repairing a plan (prototype `ask_student` mid-plan). Questions come only before planning (see 6.4).
- New eval sets beyond a planner-agent smoke set.

**Anti-goals (failure even if it "works")**
- The agent calls a plan valid. Only `verify_checked` + `check_certificate()` decide (hard rule).
- The agent writes to the plan or the record. Every change is a proposal; applying is a student action.
- An explanation that is generic ("this is a core course") instead of naming the student's interests, goals or working information.
- A course the student said they do not want comes back in a later proposal.
- Invented catalog facts (a course, an offering quarter, a prerequisite).

## 4. Constraints (from CLAUDE.md and the issues)

- Model ids only in `llm_routing.yaml`. Teamorouter's address and key only in `.env`.
- `planner_core` imports nothing from the API, the DB, HTTP or LLM clients.
- No email or IP in logs; only day-level dates. No browser request leaves the site's origin.
- Tests use `FakeLLM`. The live calls Max approved are a manual smoke run, not part of `make check`.
- `make check` and `make e2e` must pass; `make api-client` after API changes.
- Catalog-rule questions: take the strict reading, warn the student, record a default in `OPEN_QUESTIONS.md` (current phase rule).
- Accessibility: real buttons, 44 px targets, 4.5:1 contrast, visible focus, keyboard paths, `prefers-reduced-motion`.

## 5. Approaches considered

1. **Port the prototype harness (chosen by Max).** Opus writes the whole plan following the guideline; the verifier checks; Opus repairs. Best judgment on placement and interest fit. Slower (about 1-4 minutes for one plan) and costs about $0.50-1.50 per plan.
2. **Solver places, Opus picks.** Opus ranks courses, CP-SAT places them. Fast (20-40 s), always valid, but placement follows solver weights, which is what #5 complained about.
3. **Hybrid.** Like 1, but on a failed repair the solver finishes the plan. Not chosen as the main path. We keep one piece of it: the solver runs as a feasibility oracle before planning (as in the prototype), so the agent knows early whether the goals can all fit.

## 6. Design

### 6.1 `data/planner/plan-guideline.md`

One Markdown file, written for both people and the model. The harness loads all of it into the system prompt (it is cached). Rule ids are stable so the agent can cite them (`guideline:G07`) and the walkthrough can say which rule a choice follows. Tiers, highest first; when something must give, the agent bends the lowest tier first and says so.

Sections:
1. **How to use this file.** Tiers (`hard`, `strong`, `preference`, `tiebreak`), and "bend the lowest tier first and record it".
2. **Program completion (hard).** Every requirement of each declared program and the College (4200 units, Core, major) is met; credits and taken courses count first; Core courses never count toward a major; double-counting only where the catalog says so; the verifier decides. The agent reads the "unmet requirements" brief and must cover every unmet node.
3. **Offerings and sequences (hard/strong).** Only quarters in the offering data (a course with no offering data: say so, never guess); prerequisites in an earlier quarter; sequences in order and in consecutive quarters where the catalog says so (SOSC, HUMA, Civilization: no switching sequences); once-a-year starts (Autumn-only sequences) placed so no chain slips a year; course loads 300-400 units (500 only with an overload reason).
4. **The student's standards (hard/strong).** Read from `student.md` and the working information: graduation term, quarters away (abroad, internship, leave: no courses there), course load, pace, class formats they avoid, theory vs application, research. A course that breaks a hard standard is never picked; a soft one is a trade-off the agent names. Anything the student said they do not want (working information) is never proposed again.
5. **Interests (preference, but first among preferences).** Free electives, major electives and Core choices (which Humanities, Civilization, Arts sequence) follow the student's interests, career plan and research areas. Each choice names the interest it serves. Prefer forum evidence (ratings, summaries) when choosing between equal fits.
6. **Shape of a good plan (strong/preference).** The prototype's principles P05-P16, rewritten as G-rules: Core by end of year 2 (Civilization may wait), major gateways early, CS intro sequence in year 1, CMSC 27100 by the first quarter of year 3, balanced load, mix of course styles, no Humanities + SOSC + Civilization in one quarter, life events (recruiting, applications, abroad), summer only if the student agreed.
7. **CS major facts.** The CS-specific facts from `planning_facts.md` (intro sequence, theory, "on track" by end of year 3, Bx/MS timing), each with its source page.
8. **Explaining choices.** Group courses into sequences (a named sequence, a Core block, a set of electives). Each group gets a "why this for you" of 2-3 sentences that names a fact from the student record or the working information, and cites tool results (`course:`, `post:`, `summary:`, `profile:<field>`). No generic reasons.
9. **Changing the plan in chat.** Fix only what the student asked for, keep locked items, propose one change set per course or sequence, re-check prerequisites and offerings of everything that moves, record new preferences with `note_preference`, and say what the change costs (a heavier quarter, a later graduation).

Its content comes from the prototype's `principles.yaml` and `planning_facts.md` (with their sources) plus the new sections 4, 5, 8 and 9. `data/planner/config.yaml` holds the limits (questions, repair rounds, ops per round, tool calls, working-information size, budget).

### 6.2 Model routing and Teamorouter

- Teamorouter (`https://api.teamorouter.com`) speaks the Anthropic Messages API and lists `claude-opus-5-5` (checked with a free `GET /v1/models`).
- `Settings` gets an explicit optional `anthropic_base_url` (env `ANTHROPIC_BASE_URL`), passed to `anthropic.Anthropic(base_url=...)`. `.env.example` documents it. The key stays in `.env` as `ANTHROPIC_API_KEY`. (Max's main `.env` already has both.)
- `llm_routing.yaml` gets `a1_planner_agent` (generation: `claude-opus-5-5`, effort medium, `max_tokens` sized for thinking plus the full `submit_plan` call, about 16000) and `a1_planner_chat` (chat turns: `claude-opus-5-5`, effort low, about 6000). If Teamorouter rejects a request field (`refusal_fallback` beta, `output_config.effort`, `strict` tools, `cache_control`), the live smoke run shows it and the route turns that field off.
- The old tasks `a1_plan_generator*` and `a2_advisor_chat*` stay in the file until their code is removed in this change, then go.

### 6.3 Student record: interests

- New General Information question `interests` in `data/profile/questions.yaml`: group `goals`, type `list`, step 2, text "Which subjects or topics interest you most?", help with examples ("machine learning, philosophy of mind, Chinese"). Always shown (not only with research).
- New column `student_profile.interests` (JSON list, migration 0012). `render_student_md()` writes it under Goals. The dashboard agent and the dashboard read it through the question file as usual.
- A local plan keeps `profile_answers.interests` (see 6.6).

### 6.4 The planner agent (`services/api/api/agents/planner/`)

Port of `ZhihchengGao/degree-plan-agent` `harness.py` and `tools.py`, using `llm_gateway` instead of `qplan/llm.py`, `planner_core` from this repo, and the student record instead of a YAML file.

**Inputs per run:** `student.md` (from the record, or from the local plan's answers when logged out), the working information (all of it, or only related lines above the config limit), the plan state (programs, credits, taken and locked items), the requirements brief (unmet nodes, candidate courses with their usual quarters), the guideline.

**Generate mode, phases:**
1. **Intake (code).** Build the inputs. Run the solver as a feasibility oracle (its plan is never used).
2. **Ask (code + model).** If a General Information answer that planning needs is empty (`intended_programs`, `interests`, `expected_graduation_term`), send a `question` event with that question and its options from the question file. Then the model may ask at most 2 more multiple-choice questions where the record is silent on a real fork (from the prototype interview). Before each question the harness saves `RunState` in `agent_run.state` (new JSONB column) and closes the stream; the next request with `run_id` + `answer` continues from the saved state. Logged-out: the state travels in the request (signed by the server, so it cannot be edited).
3. **Fill (model).** One `submit_plan` call with every quarter, grouped: `groups[]` of `{id, title, kind (major|core|elective|minor|other), courses[{code, term}], why, rules[]}`.
4. **Verify (code).** `apply_ops` → `verify_checked` → `check_certificate()`.
5. **Repair (model, at most 5 rounds).** As in the prototype: fewest ops, bend the lowest tier, record bends; stop early on thrash (same errors 3 rounds). Groups and their "why" are updated with the ops.
6. **Explain (model, small).** Final "why this for you" per group, checked: each group's course set must match the final plan, citations must come from tool results or `profile:` fields that are not empty.
7. **Return.** A `plan` event (the whole proposed plan, the verdict, the compromise list), then one `proposal` event per group, each a `change_set` with status `proposed` for a saved plan, or the ops for a local plan. Then `done`. If repair fails, the plan is still returned as proposals with the verdict "not valid yet" and the issues, never as valid.

**Chat mode:** the same endpoint with `message`. Tools: `get_plan`, `preview_ops`, `search_courses`, `get_course`, `get_program`, `get_forum_summary`, `get_forum_posts`, `propose_change_set` (one per course or sequence, at most 3 per answer), `note_preference` (adds one dated line to the working information; for a logged-in student, written directly as the agent's note, because it is the agent's own memory and the student can see and clear it), `submit_answer {text, citations}`. Typed confirmations keep working through `confirm.py`. The scope gate (Haiku) stays.

**Endpoints:** `POST /agents/planner` replaces `POST /agents/generate` and `POST /agents/chat`; `GET /agents/planner/history?plan_id`; `DELETE /agents/planner/history?plan_id` (Clear chat). `purge_old_history()` keeps messages while the plan exists. Rate limits: generation as today (10/day account, 3/day logged out); chat as today (60 / 30).

**Profile answers from the chat:** an answer to a `question` event is stored as a `profile_proposal` (new table, status `proposed`) and shown on the dashboard to accept (Issue #17 steps 24-26, `GET /me/profile/proposals`, accept and reject endpoints). The run uses the answer at once.

**Run state.** Saved and local plans both keep the paused run in `agent_run.state` (the run id is a random UUID; `agent_run` holds no user id). The state is cleared when the run ends, and runs older than one day lose it. Answering a question continues the run and does not count as a new generation for the rate limit.

**Proposals that outlive other edits (follows from #18 D1).** Today a change set can be applied only while the plan still has its `base_plan_hash`, so accepting the first proposal of a run would make all the others stale. For planner change sets (`origin: agent`, kind `planner`) the apply endpoint instead re-bases: if the ops still apply cleanly to the current plan (no `ChangeOpError`: the added course is not already there, the moved item is still in its quarter), they are applied, and the plan is verified as usual. If not, the change set becomes `stale` and the panel says "This proposal no longer fits your plan" with **Ask again**. Typed confirmations (`confirm.py`) keep the strict hash check. Local plans follow the same rule in the browser.

**Existing courses on regeneration.** Locked and completed items stay. Other existing items that the new plan does not keep are proposed for removal as one extra group, "Courses this plan replaces", so nothing disappears without the student's accept.

**Standards the verifier does not check.** After fill and after each repair round, code adds these as errors for the repair step: a course in a quarter the student is away; a quarter above the student's `course_load`; a course on the student's "do not want" list. `note_preference` takes `{text, kind: avoid|prefer|schedule|other, courses[]}`; `avoid` lines with course codes form that list. Offering warnings (V04), Core timing (V10) and goal warnings (V11) are fixed after the errors, as in the prototype (`fix_warning_codes`).

### 6.5 Event contract (SSE, written to `docs/CONTRACTS.md` first)

```
step      {name, status: started|done|failed}
question  {run_id, question_id, field|null, text, options[], allow_other, state?}
plan      {run_id, verdict: valid|invalid, issues[], compromises[], summary}
proposal  {change_set_id|null, group_id, title, kind, ops[], why, citations[], rules[], preview}
message   {text, citations[]}
confirm   {change_set, confirmation_text}
done      {run_id}
error     {reason, message}
```

`citations[].kind` gains `profile` (`profile:interests`) and `guideline` (`guideline:G07`); `profile:` chips link to the field on the dashboard, `guideline:` chips show the rule text.

### 6.6 Local plans (logged out)

`LocalPlan` gains `chat[]`, `proposals[]` (pending, with their group, why and citations), `history[]` (applied edits with their inverse ops), `workingNotes`, `profileAnswers`. `importOnLogin.ts` copies `workingNotes` and `profileAnswers` into the record (answers as proposals) when the record is empty for that field.

### 6.7 The page

```
┌──────────────────────── Planner ─────────────────────────────┬──── Planner agent ─────┐
│ My Plan ✎   CS BS ×  + Program     Check plan ②  History  Save │ Generative AI   Clear ✕ │
│                                           [Generate plan] [Ask]│                        │
├──────────────┬──────────────┬──────────────┬──────────────────┤ ▸ Loading requirements │
│ First year   │ Second year  │ Third year   │ Fourth year      │ ▸ Writing your plan    │
│ 2026-27      │ 2027-28      │ 2028-29      │ 2029-30          │                        │
│ + Summer     │ + Summer     │ + Summer     │ + Summer         │  Step 2 of 7           │
│ Autumn       │ Autumn       │ Autumn       │ Autumn           │  Intro CS sequence     │
│ ┏━━━━━━━━━━┓ │ ┌──────────┐ │              │                  │  CMSC 14100-14400      │
│ ┃CMSC 14100┃ │ │CMSC 27100│ │              │                  │  You said you want     │
│ ┗━━━━━━━━━━┛ │ └──────────┘ │              │                  │  machine learning …    │
│ ╎MATH 15100╎ │              │              │                  │  [course:CMSC 14100]   │
│ Winter       │ Winter       │ …            │ …                │  [Accept] [Reject]     │
│ ┏━━━━━━━━━━┓ │              │              │                  │  [Back] [Next ▸]       │
│ ┃CMSC 14200┃ │              │              │                  │────────────────────────│
│ ┗━━━━━━━━━━┛ │              │              │                  │  Ask or tell me…   [➤] │
└──────────────┴──────────────┴──────────────┴──────────────────┴────────────────────────┘
 ┏━┓ glowing: the sequence the walkthrough is on    ╎ ╎ dashed: proposed, not accepted
```

- **Layout.** By default the panel is hidden and the grid uses the full width (issue #18 step 5, Richard's request). **Generate plan** and **Ask Quarterly** open it. It stays open while a walkthrough runs or proposals are pending, and remembers open/closed on this device. On screens 1024 px and wider the panel is the right third; below that it is a full-screen sheet (`components/ui/sheet.tsx`). Opening moves focus into it; Escape hides it.
- **Grid.** Four columns, one per academic year (more columns scroll sideways if the plan has a fifth year). Each column stacks Summer (a thin "+ Summer" row unless it has courses or Show Summer is on), Autumn, Winter, Spring, which keeps the project's year order (Summer before Autumn, SPEC "Planner"). Below 768 px the columns stack (one year after another). Year headings, Add a year, Graduating in, footers and goals stay.
- **Compact course card.** Code, short title (one line, truncated), units, requirement stripe. Hours and difficulty move to the card's tooltip and the details panel, because a column is about 200-230 px wide with the panel open.
- **Proposal blocks.** Dashed outline, a "Proposed" tag, the group's color dot. Removing ops show the existing card struck through with "Proposed: remove". Clicking a block selects its proposal card in the panel. Accept/Reject live on the proposal card (keyboard reachable), plus **Accept all** / **Reject all** after a generation. Accepted items get `locked = true`. Saved plan: Accept = `POST /plans/{id}/changesets/{cs}/apply`, Reject = `.../discard`. Local plan: `applyOps()` in the browser. New proposals are announced in an `aria-live` region.
- **Walkthrough.** After a generation the panel shows "Walk me through it" and starts on its own (the student can skip). Step n of N, one group per step, in plan order (major sequences, then Core, then electives). The group's blocks get a glowing outline (an animated ring in the primary color; a static ring with `prefers-reduced-motion`), the grid scrolls them into view, and the panel shows the title, the courses with their quarters, "why this for you", citation chips, the rules it follows, and Accept / Reject / Back / Next. The walkthrough can be replayed from the plan event card.
- **Chat.** Student and agent bubbles, a typing indicator, step lines during a run, `question` events as option buttons plus an "Other" text box, citation chips (`CitationChip` kept; new `profile:` and `guideline:` kinds), proposal cards, "Generative AI" label. **Clear chat** with a confirm.
- **Details panel.** Clicking a block (not a proposal) opens `CourseOverview` with student ratings in the panel area. On narrow screens it replaces the agent panel; Back returns to the chat.
- **History.** A History button opens a list of applied edits (newest first) with **Revert** on each, which applies the inverse ops (`features/planner/changes.ts`). A local plan keeps it in `localStorage`; a saved plan keeps it the same way per plan id.
- **Removed.** `GenerateDialog.tsx` and `AdvisorSheet`. The Requirements, Goals, Credits and Check plan drawer stays, and dragging courses onto the grid from Requirements and `CoursePicker` stays.

### 6.8 Testing

- Python: harness phases with `FakeLLM` (fill → verify → repair → explain, question/resume, thrash stop, invalid output repair turn), the guideline loads into the prompt, `note_preference`, citation checks with `profile:` and `guideline:`, endpoints and limits, migration 0012 up/down/up. A golden CS student (first-year, interests "machine learning, philosophy") whose fake fill plan must verify.
- Web: vitest for the grid (4 columns, Summer row), proposal blocks, walkthrough stepping and focus, history revert, local-plan storage. Playwright mock suite: `planner.spec.ts` and `agents.spec.ts` updated to the panel; the journeys in `e2e-stack/` updated (fake AI).
- Live: one manual smoke run on Teamorouter (connection and request fields), then a few CS generations to tune the guideline and the explanations. Results and costs go into `docs/LIVE-TEST-REPORT.md`.

## 7. Calls I made (Max can change them)

1. Each column stacks Summer (collapsed), Autumn, Winter, Spring, keeping the project's year order rather than Autumn-first with Summer last.
2. Hours and difficulty move off the compact card into the tooltip and the details panel.
3. No mid-plan questions this round; questions only before planning.
4. Chat turns also use Opus 5.5 (`a1_planner_chat`, effort low), since #17 makes generation and chat one agent.
5. `note_preference` writes to the working information directly (the agent's memory, visible and clearable). Profile answers go through `profile_proposal` and need the student's accept.
6. The walkthrough starts on its own after a generation, with Skip.
7. The edit history of a saved plan is also kept on the device (not on the server) in this round.
8. The `interests` question is step 2 (dashboard agent and planner chat), not on the registration form.
9. Planner proposals re-base onto later edits instead of going stale (needed for #18 D1); typed confirmations keep the strict check.
10. Regenerating a plan proposes removing unlocked existing courses as one group instead of removing them silently.
11. Code (not only the model) enforces quarters away, course load and the "do not want" list.
12. A student with no intended program gets the `intended_programs` question first; the guideline and tests are tuned for CS.

## 8. Left to the builder

Exact component split, Tailwind classes within `docs/DESIGN.md`, the glow animation details, prompt wording beyond the guideline, the requirement-brief format, how working-information lines are matched when over the size limit (keyword overlap is fine), and the order of commits.
