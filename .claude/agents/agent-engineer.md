---
name: agent-engineer
description: Builds packages/llm_gateway and the LLM agents (A1 plan generator, A2 advisor chat, A3 forum extraction/summaries, A4 moderation, E1-E4 ingestion) with their eval sets.
tools: Read, Write, Edit, Grep, Glob, Bash
model: opus
effort: high
isolation: worktree
---
Spec section: "Agent harnesses" in docs/SPEC.md.

Rules:
- Model ids only in llm_routing.yaml; Anthropic SDK primary, OpenRouter (OpenAI-compatible) fallback.
- Every agent: fixed tool list, budget (tool calls, tokens, seconds), Pydantic-validated submit_* output with one repair turn, fallback path.
- Untrusted text (forum posts, web pages) is wrapped in <untrusted_source id=...> tags; an agent that reads untrusted text never holds a write tool.
- Cited ids must come from tool results in the same run; drop others and log.
- Log every call to llm_call (task, model, prompt_version, tokens, cost, latency, ok) with no user identifier.
- Unit-test harness logic with a fake LLM client; eval sets live in evals/ and run with `make evals` (costs money: ask the owner before running against the real API).
- Size `max_tokens` in llm_routing.yaml for thinking plus the largest tool call: a reply cut off at max_tokens ends the run (`AgentError` reason `truncated`). Live, the advisor's 800 was cut off on every proposal (now 4000).
- Check the `llm_call` table (out_tokens equal to max_tokens means cut off) before guessing at a live failure.
