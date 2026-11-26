"""llm_routing.yaml is the only place model ids live; check it is well formed."""

from pathlib import Path

import yaml

ROUTING = Path(__file__).resolve().parents[3] / "llm_routing.yaml"
REQUIRED_TASKS = {
    "e3_program_formalizer",
    "e3b_second_opinion",
    "e2_program_enumerator",
    "e1_prereq_formalizer",
    "e4_backtranslation_judge",
    "scraper_repair",
    "dept_offerings_extraction",
    "a1_plan_generator",
    "a2_advisor_chat",
    "a2_advisor_chat_escalation",
    "a2_scope_classifier",
    "a3_forum_extraction",
    "a3_forum_summary",
    "a3_cold_start_estimate",
    "a4_moderation",
}


def test_routing_file_lists_every_task_with_model_and_fallback() -> None:
    data = yaml.safe_load(ROUTING.read_text())
    tasks = data["tasks"]
    assert set(tasks) >= REQUIRED_TASKS
    for name, row in tasks.items():
        assert row["model"].startswith("claude-"), name
        assert row["max_tokens"] > 0, name
        assert row["fallback"]["provider"] == "openrouter", name
        assert row["effort"] in {None, "low", "medium", "high", "xhigh", "max"}, name


def test_llm_gateway_imports() -> None:
    import llm_gateway

    assert llm_gateway.__version__


def test_routing_has_planner_tasks() -> None:
    from llm_gateway.routing import load_routing

    routing = load_routing()
    agent = routing.route("a1_planner_agent")
    assert (agent.model, agent.effort, agent.max_tokens) == ("claude-opus-5-5", "medium", 16000)
    chat = routing.route("a1_planner_chat")
    assert (chat.model, chat.effort, chat.max_tokens) == ("claude-opus-5-5", "low", 6000)
    for route in (agent, chat):
        assert route.fallback is not None
        assert route.fallback.model == "anthropic/claude-opus-5.5"
