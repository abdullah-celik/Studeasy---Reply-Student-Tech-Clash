import random

from app.agents.reels import QuizGen
from app.schemas import ReelFeed
from app.services.reels import arrange, clean_quiz, insert_break, pick_concepts

MASTERY = [
    {"concept": "Calvin cycle", "score": 0.8, "attempts": 3},
    {"concept": "Photolysis", "score": 0.1, "attempts": 1},
    {"concept": "RuBisCO", "score": 0.1, "attempts": 0},
    {"concept": "Chlorophyll", "score": 0.5, "attempts": 2},
]


def test_pick_concepts_starts_with_weakest_and_prefers_not_recently_shown():
    picks = pick_concepts(MASTERY, {"Photolysis": 3}, n=2, rng=random.Random(0))
    assert picks[0] == "RuBisCO"  # tie on score, shown less recently
    assert len(picks) == 2 and len(set(picks)) == 2


def test_pick_concepts_empty():
    assert pick_concepts([], {}) == []


def test_clean_quiz():
    mcq = QuizGen(question="q", kind="multiple_choice", options=["A", "B"], answer="b",
                  explanation="e")
    assert clean_quiz(mcq)["answer"] == "B"
    bad = mcq.model_copy(update={"answer": "Z"})
    assert clean_quiz(bad) is None
    tf = QuizGen(question="q", kind="true_false", options=[], answer="False", explanation="e")
    assert clean_quiz(tf)["options"] == ["true", "false"]


def test_arrange_puts_due_cards_after_first_group():
    g1, g2, due = [{"n": 1}, {"n": 2}], [{"n": 3}], [{"n": "due"}]
    assert [r["n"] for r in arrange([g1, g2], due)] == [1, 2, "due", 3]
    assert arrange([], due) == due


def test_insert_break_once_at_session_multiple():
    items = [{"i": i} for i in range(6)]
    out = insert_break(items, session_reels=13, break_every=15, stats={"minutes": 9})
    assert len(out) == 7
    assert out[2]["type"] == "break"  # 13 + 2 = 15 reels watched
    assert out[2]["content"]["reels_watched"] == 15


def test_no_break_at_session_start():
    items = [{"i": i} for i in range(3)]
    assert insert_break(items, 0, 15, {}) == items


def test_feed_schema_hides_quiz_answer():
    feed = ReelFeed.model_validate(
        {
            "session_reels": 0,
            "break_every": 15,
            "items": [
                {
                    "type": "quiz",
                    "id": "00000000-0000-0000-0000-000000000001",
                    "concept": "c",
                    "content": {"question": "q", "kind": "true_false",
                                "options": ["true", "false"], "answer": "true",
                                "explanation": "e"},
                },
                {"type": "break", "content": {"title": "t", "message": "m", "reels_watched": 15,
                                              "minutes": 9, "concepts": []}},
            ],
        }
    )
    dumped = feed.model_dump()
    assert "answer" not in dumped["items"][0]["content"]
    assert dumped["items"][1]["type"] == "break"
