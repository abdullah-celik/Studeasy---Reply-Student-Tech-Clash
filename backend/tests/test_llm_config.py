from langchain_core.messages import HumanMessage

from app.agents.orchestrator import Route
from app.config import get_settings
from app.llm import _model, chat_model


def test_defaults_target_gpt_6_luna_without_temperature():
    s = get_settings()
    assert s.openai_chat_model == "gpt-6-luna"
    assert s.openai_temperature is None


def test_tutor_request_uses_reasoning_effort():
    p = chat_model()._get_request_payload([HumanMessage("hi")])
    assert p["model"] == "gpt-6-luna"
    assert p["reasoning_effort"] == "low"
    assert "temperature" not in p


def test_structured_request_sends_effort_none():
    bound = _model("none").bind_tools([Route], tool_choice="Route")
    p = bound.bound._get_request_payload([HumanMessage("hi")], **bound.kwargs)
    effort = p.get("reasoning", {}).get("effort") or p.get("reasoning_effort")
    assert effort == "none"
