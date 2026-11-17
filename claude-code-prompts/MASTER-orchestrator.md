# Master prompt · Orchestrate milestone M1 with subagents

> Use this instead of pasting prompts 00-05 one by one, if you want Claude Code to run the first milestone itself. Recommended: Opus 5.5 at `xhigh` as the orchestrator; it delegates to the subagents in `.claude/agents/`. It stops at the M1 gate for your review.

---

You are the lead engineer for QuadPlan. Read `CLAUDE.md`, `docs/SPEC.md` sections "Summary and decisions to confirm" and "Build roadmap and Claude Code prompt sequence", and the prompt files in `claude-code-prompts/`.

Your job is milestone M1: a working planner with the verifier on hand-verified seed data, and no AI features. Execute it like this:

1. **Sequential foundation.** Do `claude-code-prompts/00-bootstrap.md`, then `01-contracts.md`, yourself in this session. Each must end with `make check` passing and the `spec-reviewer` subagent's findings fixed. Commit after each with a clear message.
2. **Parallel build.** Once 01 is committed, launch four subagents at the same time, each in its own worktree, each given the full text of its prompt file:
   - `verifier-engineer` <- `02-verifier.md`
   - `frontend-engineer` <- `03-frontend-shell.md`
   - a general subagent at Fable 5.2 <- `04-accounts.md` (then `security-privacy-reviewer` on its diff)
   - `data-curator` <- `05-seed-data.md`
3. **Integrate.** Merge each worktree branch when its checks pass. Resolve conflicts in favour of the contracts from prompt 01; if a contract must change, change it once, regenerate the API client, and tell the other subagents.
4. **M1 gate.** With everything merged: `make up`, `make seed`, `make check`, `make golden`, `make e2e`. Then the `spec-reviewer` subagent on the whole M1 scope.
5. **Stop.** Write `docs/PROGRESS.md` with what works, screenshots of the planner with seed data, the open questions, and `data/seed/REVIEW.md` for Richard to check. Do not start prompt 06 until Richard replies.

Rules for the whole run:
- Show evidence (command output, test counts, screenshots), not claims.
- Never invent catalog facts; open questions go to `docs/OPEN_QUESTIONS.md`.
- Do not call the real Anthropic or OpenRouter APIs in M1.
- If two attempts at the same fix fail, stop and summarize the problem instead of looping.
