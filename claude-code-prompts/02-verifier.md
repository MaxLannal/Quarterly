# Prompt 02 · Verification engine (planner_core)

> Recommended: Fable 5.2 (or Opus 5.5 at `xhigh`). Delegate to the `verifier-engineer` subagent (it runs in its own worktree). Can run in parallel with 03, 04 and 05.

---

Use the verifier-engineer subagent for this task. Context: `CLAUDE.md`, SPEC "Requirements DSL" and "Verification engine (non-agentic)", and the models from prompt 01.

Build in `packages/planner_core`:
1. **Expression evaluation** for prerequisites and co-requisites with the exact semantics in the spec (strictly earlier term; co-requisite same or earlier; consent = warning; credits count).
2. **Checks V01-V12**, each a pure function returning Issue objects with stable codes, messages and `fix_hints`.
3. **CP-SAT program model** (OR-Tools) for V07/V08: variables x[c,n], s[n], y[c,P]; node semantics for slot, select (count and units), group (all / n_of), bounded_parts, same_sequence, max_from, distinct_subjects; share limits across programs; objective 1 = maximize weighted satisfied nodes, objective 2 = minimize courses used. Return the minimal unmet set when unsatisfiable.
4. **Certificate builder** and **`check_certificate()`**: linear time, no solver import, under ~300 lines, readable.
5. **Goal predicates** for every goal type in the spec's table.
6. **`verify(plan, rules, catalog, options) -> Report`** orchestrating all of the above. Pure function.
7. Wire `POST /verify` in the API: load the RuleSet from Postgres, call `verify`, cache the Report in Redis by `plan_hash`.

Tests (write them first):
- One fixture per edge case: cross-listed duplicate; mutually exclusive pair; prerequisite in the same term (error) vs co-requisite in the same term (ok); consent (warning); `p_offered` < 0.3 (warning); 500 units with and without an overload reason; minor sharing with a major and with the Core; bounded_parts 2-3 / 2-3 / 1-2 summing to 6, satisfiable and not; same_sequence; a Bx/MS share limit; 4200 units with 3800 by enrollment; each goal type.
- Hypothesis: every certificate from the solver passes `check_certificate`; mutations (drop a course, move it one term earlier, add a fifth course) produce the expected codes.
- Benchmark: 60 courses, 200 nodes, 3 programs under 300 ms; print the timing.

Done when `make check` passes with planner_core coverage at 95% or higher. Run `spec-reviewer`, fix findings, update `docs/PROGRESS.md`.
