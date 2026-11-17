# Prompt 12 · Hardening and pilot launch prep

> Recommended: Opus 5.5, effort `xhigh`.

---

Context: `CLAUDE.md`, SPEC "Core user journeys", "Risks, policy and legal", "Accounts and anonymity".

Do:
1. Playwright end-to-end tests for journeys A-D in the spec, against the Docker stack with seed data and FakeLLM.
2. Run the `security-privacy-reviewer` subagent over the whole repository; fix high and medium findings; list the rest in `docs/OPEN_QUESTIONS.md`.
3. Load test (locust or k6): POST /verify at 50 requests/second with p95 under 500 ms; forum page reads at 100 requests/second.
4. Content pages: `/privacy` (what is stored, honest limits, from the spec), `/guidelines` (community rules), `/about`; the "Not official advising" banner on every plan.
5. Ops: nightly encrypted Postgres backup script; `docs/DEPLOY.md` for a single VM with Docker Compose and Caddy (TLS); daily LLM spend alarm from `llm_call`.
6. Final pass with `spec-reviewer` on the whole spec: list anything specified but not built.

Done when every check passes. Write a launch checklist in `docs/PROGRESS.md` for Richard.
