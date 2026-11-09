from app.agents.quiz import GeneratedDeck, GeneratedQuiz
from app.agents.reels import QuizGen


def test_quiz_accepts_typical_llm_quirks():
    quiz = GeneratedQuiz.model_validate(
        {
            "questions": [
                {
                    "type": "True/False",
                    "prompt": "Water is split in photolysis",
                    "options": None,
                    "answer": True,
                    "explanation": "Yes",
                    "concept": "Photolysis",
                    "source_indices": ["[1]", 2],
                },
                {
                    "type": "multiple choice",
                    "prompt": "Where?",
                    "options": ["Stroma", "Nucleus"],
                    "answer": "Stroma",
                    "concept": "Calvin cycle",
                },
                {"type": "open", "prompt": "Explain", "answer": 42, "concept": "ATP"},
            ]
        }
    )
    tf, mc, open_q = quiz.questions
    assert (tf.type, tf.answer, tf.options, tf.source_indices) == ("true_false", "true", [], [1, 2])
    assert mc.type == "multiple_choice" and mc.explanation == ""
    assert open_q.answer == "42"


def test_deck_and_reel_quiz_coerce():
    deck = GeneratedDeck.model_validate({"cards": [{"front": 1, "back": False, "concept": "c"}]})
    assert deck.cards[0].back == "false"
    q = QuizGen.model_validate({"question": "q", "kind": "true_false", "answer": False})
    assert q.answer == "false" and q.options == []
