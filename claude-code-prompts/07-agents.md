# Prompt 07 · LLM gateway, plan-generator agent and advisor chat

> Recommended: Opus 5.5, effort `high`, via the `agent-engineer` subagent. Parallel with 08. Needs ANTHROPIC_API_KEY in `.env` for the real-API evals only.

---

Use the agent-engineer subagent. Context: `CLAUDE.md`, SPEC "Agent harnesses" (all of it), "Accounts and anonymity" (rate limits), and prompt 06's generator.

Build:
1. **`packages/llm_gateway`:** Anthropic Python SDK client; OpenRouter client (OpenAI-compatible) as fallback after two provider errors; routing from `llm_routing.yaml`; prompt caching for system prompts and schemas; structured outputs validated with Pydantic plus one repair turn; budgets (tool calls, tokens, seconds); `llm_call` logging with cost. A `FakeLLM` for tests that replays scripted tool calls.
2. **A1 plan generator:** step 3 (elective preferences: `search_courses`, `get_course`, `get_forum_summary`, `submit_preferences`, budget 12 tool calls) and step 6 (rationale: <= 25 words per quarter, citations validated, course set must match) around prompt 06's solver; fallbacks exactly as specified; SSE progress events; limits 10/day per account, 3/day logged-out (Redis counter, 24 h TTL, never persisted).
3. **A2 advisor chat:** Haiku scope classifier (`in_scope`, `off_topic`, `confirmation`, `suspicious`) with a fixed refusal for off-topic; read tools (`get_plan`, `preview_ops`, `search_courses`, `get_course`, `get_program`, `get_forum_summary`, `get_forum_posts`, `compare_courses`); one draft tool `propose_change_set`; NO write tool. A deterministic confirmation parser ("I agree to add/move/remove <codes> to/from <terms>", "apply it") that applies only when the parsed ops equal the latest proposal or are fully explicit, and the plan hash matches. Answers as `{text, citations[]}`; drop citations not returned by a tool in this run. History per plan, deleted after 30 days.
4. **Prompts** in `prompts/a1_preferences.md`, `prompts/a1_rationale.md`, `prompts/a2_chat.md`, `prompts/a2_scope.md`, each with a version header. Untrusted forum text wrapped in `<untrusted_source id=...>`.
5. **Evals** in `evals/`: A1 50 profiles; A2 60 in-scope, 20 off-topic, 10 confirmations, 10 injection attempts hidden in forum fixtures. `make evals` runs them against the real API with a cost cap; ask Richard before running it.
6. Connect the frontend Generate popup and Advisor panel to the real endpoints; remove their MSW mocks.

Tests with FakeLLM: budget exhaustion -> fallback; invalid output -> one repair -> fail; fabricated citation dropped; injection text cannot cause a write; confirmation parser cases.

Done when `make check` passes. Run `spec-reviewer` and `security-privacy-reviewer`, fix findings, update `docs/PROGRESS.md`.
