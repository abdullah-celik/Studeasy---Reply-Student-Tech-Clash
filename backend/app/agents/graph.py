"""The multi-agent chat graph.

    START -> orchestrator --explain--> retrieve -> tutor -> verifier -> END
                          --chitchat-> tutor -> END
                          --quiz-----> quiz_master -> END
                          --plan-----> planner -> END

The Supabase client is passed per run via config["configurable"]["db"].
"""

import logging
from functools import lru_cache

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents import orchestrator, tutor, verifier
from app.agents.state import ChatState
from app.config import get_settings
from app.errors import NoMaterialError
from app.services import planning, quizzes, retrieval

log = logging.getLogger(__name__)

CHAT_QUIZ_TYPES = ["multiple_choice", "true_false", "open"]
CHAT_QUIZ_COUNT = 5


def _db(config: RunnableConfig):
    return config["configurable"]["db"]


async def orchestrator_node(state: ChatState, config: RunnableConfig) -> dict:
    r = await orchestrator.route(state["message"], state.get("history", []), config)
    return {"intent": r.intent, "topic": r.topic}


async def retrieve_node(state: ChatState, config: RunnableConfig) -> dict:
    query = state["message"] if not state.get("topic") else f"{state['topic']}: {state['message']}"
    chunks = await retrieval.search(_db(config), state["user_id"], state["course_id"], query)
    return {
        "sources": retrieval.public_sources(chunks),
        "sources_text": retrieval.format_sources(chunks),
    }


async def tutor_node(state: ChatState, config: RunnableConfig) -> dict:
    # chitchat skips retrieval -> sources_text is None -> friendly short reply
    sources_text = state.get("sources_text") if state.get("intent") == "explain" else None
    msg = await tutor.answer(state["message"], state.get("history", []), sources_text, config)
    return {"answer": msg.content if isinstance(msg.content, str) else str(msg.content)}


async def verifier_node(state: ChatState, config: RunnableConfig) -> dict:
    v = await verifier.verify(state["answer"], state["sources_text"], config)
    return {"verification": v.model_dump()}


async def quiz_node(state: ChatState, config: RunnableConfig) -> dict:
    try:
        quiz = await quizzes.create_quiz(
            _db(config),
            state["user_id"],
            state["course_id"],
            state.get("topic"),
            CHAT_QUIZ_TYPES,
            CHAT_QUIZ_COUNT,
        )
        return {"quiz": quiz}
    except NoMaterialError as e:
        return {"error": e.message}
    except Exception:
        log.exception("Quiz generation from chat failed")
        return {"error": "I couldn't build a quiz this time. Please try again."}


async def planner_node(state: ChatState, config: RunnableConfig) -> dict:
    plan = await planning.make_plan(_db(config), state["user_id"], state["course_id"])
    return {"plan": plan.model_dump(mode="json")}


def _after_orchestrator(state: ChatState) -> str:
    return {
        "explain": "retrieve",
        "quiz": "quiz_master",
        "plan": "planner",
    }.get(state.get("intent", "chitchat"), "tutor")


def _after_tutor(state: ChatState) -> str:
    if state.get("intent") == "explain" and state.get("sources") and get_settings().verify_answers:
        return "verifier"
    return END


@lru_cache
def build_graph():
    g = StateGraph(ChatState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("tutor", tutor_node)
    g.add_node("verifier", verifier_node)
    g.add_node("quiz_master", quiz_node)
    g.add_node("planner", planner_node)

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges(
        "orchestrator", _after_orchestrator, ["retrieve", "tutor", "quiz_master", "planner"]
    )
    g.add_edge("retrieve", "tutor")
    g.add_conditional_edges("tutor", _after_tutor, ["verifier", END])
    g.add_edge("verifier", END)
    g.add_edge("quiz_master", END)
    g.add_edge("planner", END)
    return g.compile()
