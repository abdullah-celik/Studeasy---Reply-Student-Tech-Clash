import io
from datetime import date

import pytest

from app.agents.quiz import GeneratedQuestion
from app.services.ingestion import chunk_sections, extract_sections
from app.services.mastery import updated_score
from app.services.planning import MAX_DAYS, plan_dates
from app.services.quizzes import _clean_question


def test_extract_text_and_chunk():
    text = ("Photosynthesis converts light into chemical energy. " * 60).encode()
    sections = extract_sections("notes.md", text)
    chunks = chunk_sections(sections)
    assert len(chunks) > 1
    assert all(c.location == "text" for c in chunks)


def test_extract_docx_splits_on_headings():
    from docx import Document

    doc = Document()
    doc.add_heading("Cells", level=1)
    doc.add_paragraph("Cells are the basic unit of life.")
    doc.add_heading("Energy", level=1)
    doc.add_paragraph("ATP stores energy.")
    buf = io.BytesIO()
    doc.save(buf)

    sections = extract_sections("notes.docx", buf.getvalue())
    assert [s.location for s in sections] == ["section: Cells", "section: Energy"]


def test_extract_pptx_uses_slide_numbers():
    from pptx import Presentation

    prs = Presentation()
    for title in ("Intro", "Mitochondria"):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = title
    buf = io.BytesIO()
    prs.save(buf)

    sections = extract_sections("deck.pptx", buf.getvalue())
    assert [s.location for s in sections] == ["slide 1", "slide 2"]
    assert "Mitochondria" in sections[1].text


def test_unsupported_extension():
    with pytest.raises(ValueError):
        extract_sections("image.png", b"")


def test_mastery_moving_average():
    assert updated_score(0.0, 0, 1.0) == 1.0  # first attempt replaces the seed score
    assert updated_score(1.0, 1, 0.0) == 0.7


def test_plan_dates_until_exam_and_capped():
    today = date(2026, 11, 7)
    assert len(plan_dates(today, [{"exam_date": "2026-11-10"}], None)) == 3
    assert len(plan_dates(today, [{"exam_date": "2027-01-10"}], None)) == MAX_DAYS
    assert len(plan_dates(today, [], None)) == 7


def _q(**kw):
    base = dict(type="multiple_choice", prompt="p", options=["A", "B"], answer="b",
                explanation="e", concept="c")
    return GeneratedQuestion(**{**base, **kw})


def test_clean_question_repairs_and_rejects():
    assert _clean_question(_q(), {"multiple_choice"})["answer"] == "B"
    assert _clean_question(_q(answer="Z"), {"multiple_choice"}) is None
    assert _clean_question(_q(type="true_false", answer="True"), {"true_false"})["answer"] == "true"
    assert _clean_question(_q(), {"open"}) is None


# History summaries -------------------------------------------------------------
def test_summarize_quiz_uses_latest_answer_per_question():
    from app.services.quizzes import summarize_quiz

    row = {
        "id": "q1",
        "topic": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "questions": [
            {"id": "a", "answers": [
                {"score": 0.0, "created_at": "2026-01-01T10:00:00+00:00"},
                {"score": 1.0, "created_at": "2026-01-01T11:00:00+00:00"},
            ]},
            {"id": "b", "answers": [{"score": 0.5, "created_at": "2026-01-01T10:00:00+00:00"}]},
            {"id": "c", "answers": []},
        ],
    }
    s = summarize_quiz(row)
    assert (s["question_count"], s["answered_count"]) == (3, 2)
    assert s["score"] == 0.75


def test_summarize_quiz_without_answers():
    from app.services.quizzes import summarize_quiz

    s = summarize_quiz({"id": "q", "topic": "x", "created_at": "t", "questions": []})
    assert s["answered_count"] == 0 and s["score"] is None


def test_summarize_deck_counts_due_cards():
    from datetime import UTC, datetime

    from app.services.quizzes import summarize_deck

    now = datetime(2026, 1, 2, tzinfo=UTC)
    row = {
        "id": "d",
        "topic": None,
        "created_at": "t",
        "flashcards": [
            {"due_at": "2026-01-01T00:00:00+00:00"},
            {"due_at": "2026-01-03T00:00:00+00:00"},
        ],
    }
    s = summarize_deck(row, now)
    assert (s["card_count"], s["due_count"]) == (2, 1)


def test_chat_title_is_trimmed():
    from app.services.chat_history import TITLE_MAX, title_from

    assert title_from("  Explain   photosynthesis\nplease ") == "Explain photosynthesis please"
    long = title_from("word " * 40)
    assert len(long) <= TITLE_MAX and long.endswith("…")
