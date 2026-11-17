# Prompt 06 · Deterministic plan generator and change sets

> Recommended: Opus 5.5, effort `xhigh`. Runs after 02 and 05 are merged.

---

Context: `CLAUDE.md`, SPEC "Agent harnesses" (A1 steps 1, 2, 4, 5, 7), "Verification engine" (goal predicates), and planner_core from prompt 02.

Build in planner_core (pure) and the API:
1. **Goal compiler:** each goal type -> hard bounds, rewards or penalties exactly as the goal table says.
2. **Placement model (CP-SAT):** place[c, t] variables; prerequisite order; `p_offered` >= 0.3 unless the student overrides; loads and overload rules; locked and completed items fixed; program satisfaction reusing the V07 model; objective = preference weights + goal rewards - penalties for workload spikes. Produce up to 3 variants, each differing from earlier ones in at least 4 placements.
3. **Infeasibility explanation:** use assumption literals for goals and soft limits so an infeasible request names the smallest set of goals to relax, in plain English ("Graduating by Spring 2029 needs 5 more courses than your remaining quarters allow").
4. **Default preferences** (no LLM): interest-tag match, then forum `recommend_rate`, then course level.
5. Every variant goes through `verify` + `check_certificate`; a failure raises an alert and drops the variant.
6. **Change sets:** create from a variant (ops + `base_plan_hash` + preview report); apply only if the plan hash still matches, else mark `stale` and re-preview; discard.
7. Endpoint `POST /plans/{id}/generate?mode=deterministic` for testing without an LLM; wire the Generate popup to it behind a feature flag until prompt 07.

Tests: 20 synthetic student profiles (first-year undecided, transfer, CS+Math+Bx/MS, pre-med-like timing, study abroad block, graduate early) -> every result is a verified plan or a correct infeasibility explanation; generation under 5 s each.

Done when `make check` passes. Run `spec-reviewer`, fix findings, update `docs/PROGRESS.md`.
