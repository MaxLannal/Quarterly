import pytest
from llm_gateway.api import FakeLLM, LLMUnavailableError, Message, UnavailableLLM, get_llm, set_llm
from pydantic import BaseModel


class Label(BaseModel):
    label: str


def test_fake_llm_replays_answers_and_records_calls() -> None:
    fake = FakeLLM(
        script={"a4_moderation": [{"label": "ok"}, Label(label="spam"), TimeoutError("slow")]}
    )
    msgs = [Message("user", "hi")]
    kw = {"system": "s", "messages": msgs, "schema": Label, "prompt_version": "v1"}
    assert fake.structured("a4_moderation", **kw).label == "ok"
    assert fake.structured("a4_moderation", **kw).label == "spam"
    with pytest.raises(TimeoutError):
        fake.structured("a4_moderation", **kw)
    with pytest.raises(LLMUnavailableError):
        fake.structured("a4_moderation", **kw)
    assert [c["task"] for c in fake.calls] == ["a4_moderation"] * 4


def test_default_client_refuses_and_can_be_replaced() -> None:
    assert isinstance(get_llm(), UnavailableLLM)
    with pytest.raises(LLMUnavailableError):
        get_llm().structured("x", system="", messages=[], schema=Label, prompt_version="v1")
    fake = FakeLLM()
    set_llm(fake)
    try:
        assert get_llm() is fake
    finally:
        set_llm(UnavailableLLM())
