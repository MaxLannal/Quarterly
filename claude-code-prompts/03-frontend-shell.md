# Prompt 03 · Frontend shell and planner UI

> Recommended: Opus 5.5, effort `high`. Delegate to the `frontend-engineer` subagent (own worktree). Parallel with 02, 04, 05.

---

Use the frontend-engineer subagent. Context: `CLAUDE.md`, SPEC "Sitemap and every page", the generated API client from prompt 01, and the mockups linked in that section (planner, generate popup, course page, forum, onboarding, sign-up).

Build in `apps/web`:
1. App shell: header, nav (Plan, Courses, Programs, Forum), search box, login button; responsive down to phone width.
2. **Planner page** exactly as specified: top bar (programs, verifier badge, Generate plan, Save); requirement rail with progress per node; 4-year grid (Autumn, Winter, Spring; collapsible Summer; optional Year 5); course cards (code, title, requirement tag, hours, difficulty); quarter footers (units, hours, difficulty); right rail tabs Issues / Goals / Advisor. Drag and drop with dnd-kit plus a keyboard "Move to..." menu; right-click or menu for lock, mark completed, remove. Debounced (300 ms) POST /verify after every edit; issues highlight their cards.
3. **Generate popup** (form only; submits to /agents/generate) and the results list with Apply / View diff.
4. **Advisor panel** UI: message list, citation chips, proposal cards with Apply / Dismiss.
5. **Onboarding** wizard (5 steps) and **Course search / Course page** with prerequisite mini-graph, offerings table and attribute card.
6. Mock every not-yet-built endpoint with MSW using the generated types; list each mock in `docs/OPEN_QUESTIONS.md` so it gets removed later.
7. Logged-out plan in localStorage (try/catch around every access); import on login.

Tests: vitest for plan state logic (drag, lock, debounce); one Playwright test per page; an axe accessibility check on the planner.

Done when `make check` and `make e2e` pass. Run `spec-reviewer`, fix findings, update `docs/PROGRESS.md`.
