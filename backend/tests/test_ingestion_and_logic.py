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
