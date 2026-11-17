# QuadPlan starter kit for Claude Code

Everything a coding agent needs to start building QuadPlan (UChicago course planner + course forum) in VS Code with Claude Code and Docker.

## What is here

| Path | What it is |
| --- | --- |
| `docs/SPEC.md` | The full product and technical spec, exported from the shared Claude doc. Edit either copy, but keep them in sync. |
| `CLAUDE.md` | Short project rules Claude Code reads at the start of every session. |
| `.claude/agents/` | Six subagents: `spec-reviewer`, `verifier-engineer`, `frontend-engineer`, `data-curator`, `agent-engineer`, `security-privacy-reviewer`. |
| `claude-code-prompts/00-12` | The build, one prompt per step. Paste them in order. |
| `claude-code-prompts/MASTER-orchestrator.md` | One prompt that runs milestone M1 (steps 00-05) with parallel subagents and stops for your review. |

## How to start

1. Unzip into an empty folder, then `git init` and make a first commit.
2. Install Docker Desktop, Node 20+, Python 3.12 and `uv`.
3. Copy `.env.example` to `.env` after prompt 00 creates it; add `ANTHROPIC_API_KEY` (needed from prompt 07 on) and optionally `OPENROUTER_API_KEY`.
4. Open the folder in VS Code and start Claude Code.
5. Pick the model with `/model` before each prompt, as each prompt's header recommends. Effort levels are `low`, `medium`, `high`, `xhigh`, `max`; the `CLAUDE_CODE_EFFORT_LEVEL` environment variable also sets it. "Opus 5.5 extra" = Opus 5.5 at `xhigh`.
6. Paste `00-bootstrap.md`, let it finish, check the evidence it shows you, commit. Continue in order, or use the master prompt for M1.

## Order and parallelism

| Milestone | Prompts | Notes |
| --- | --- | --- |
| M1 · planner without AI | 00, 01, then 02-05 in parallel | Review `data/seed/REVIEW.md` yourself before M2 |
| M2 · generation and chat | 06, then 07 | 07 needs your API key; evals cost money |
| M3 · forum | 08 (parallel with 07), then 11 | Needs accounts from 04 |
| M4 · data and launch | 09, 10, 12 | 10 stays switched off until the University permits scraping |

## Before you build, decide

The first section of `docs/SPEC.md` lists 12 default decisions (stack, anonymity model, scope, data sources). Change any you disagree with in the spec first; every prompt reads it.
