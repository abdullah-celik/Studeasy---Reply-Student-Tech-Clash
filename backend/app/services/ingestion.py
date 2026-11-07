"""Content pipeline: file bytes -> text sections -> chunks -> embeddings -> Supabase.

Originals are not stored (decision: parse, embed, discard).
"""

import asyncio
import io
import logging
from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.llm import embeddings
from supabase import AsyncClient

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".md"}
EMBED_BATCH = 100
INSERT_BATCH = 200


@dataclass
class Section:
    text: str
    location: str  # human-readable place in the file, used in citations


def extract_sections(filename: str, data: bytes) -> list[Section]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _pdf(data)
    if ext == ".pptx":
        return _pptx(data)
    if ext == ".docx":
        return _docx(data)
    if ext in {".txt", ".md"}:
        return [Section(data.decode("utf-8", errors="replace"), "text")]
    raise ValueError(f"Unsupported file type: {ext}")


def _pdf(data: bytes) -> list[Section]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return [
        Section(page.extract_text() or "", f"page {i}")
        for i, page in enumerate(reader.pages, start=1)
    ]


def _pptx(data: bytes) -> list[Section]:
    from pptx import Presentation

    prs = Presentation(io.BytesIO(data))
    sections = []
    for i, slide in enumerate(prs.slides, start=1):
        parts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame
            if notes is not None and notes.text.strip():
                parts.append(f"Speaker notes: {notes.text}")
        sections.append(Section("\n".join(parts), f"slide {i}"))
    return sections


def _docx(data: bytes) -> list[Section]:
    """Split a Word document at its headings so citations say which section."""
    from docx import Document

    doc = Document(io.BytesIO(data))
    sections: list[Section] = []
    heading, buf = "start", []
    for p in doc.paragraphs:
        style = (p.style.name if p.style is not None else "") or ""
        if style.startswith("Heading") and p.text.strip():
            if buf:
                sections.append(Section("\n".join(buf), f"section: {heading}"))
            heading, buf = p.text.strip(), []
        elif p.text.strip():
            buf.append(p.text)
    if buf:
        sections.append(Section("\n".join(buf), f"section: {heading}"))
    return sections


def chunk_sections(sections: list[Section]) -> list[Section]:
    s = get_settings()
    splitter = RecursiveCharacterTextSplitter(chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap)
    chunks = []
    for sec in sections:
        for piece in splitter.split_text(sec.text):
            if piece.strip():
                chunks.append(Section(piece, sec.location))
    return chunks


async def process_document(
    db: AsyncClient, document_id: str, user_id: str, course_id: str, filename: str, data: bytes
) -> None:
    """Background job started by the upload endpoint. Sets status ready/failed."""
    # Imported here to avoid a circular import (the content agent uses the LLM layer).
    from app.agents.content import extract_concepts
    from app.services.mastery import seed_concepts

    try:
        sections = await asyncio.to_thread(extract_sections, filename, data)
        chunks = chunk_sections(sections)
        if not chunks:
            raise ValueError("No text could be extracted (is it a scanned PDF?)")

        texts = [c.text for c in chunks]
        vectors: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            vectors.extend(await embeddings().aembed_documents(texts[i : i + EMBED_BATCH]))

        rows = [
            {
                "user_id": user_id,
                "course_id": course_id,
                "document_id": document_id,
                "content": c.text,
                "location": c.location,
                "embedding": v,
            }
            for c, v in zip(chunks, vectors, strict=True)
        ]
        for i in range(0, len(rows), INSERT_BATCH):
            await db.table("chunks").insert(rows[i : i + INSERT_BATCH]).execute()

        # Content agent: find the key concepts so the mastery map has something to track.
        try:
            concepts = await extract_concepts(texts)
            await seed_concepts(db, user_id, course_id, concepts)
        except Exception:  # concepts are nice-to-have; don't fail the upload
            log.exception("Concept extraction failed for document %s", document_id)

        await (
            db.table("documents")
            .update({"status": "ready", "chunk_count": len(rows), "error": None})
            .eq("id", document_id)
            .execute()
        )
    except Exception as exc:
        log.exception("Ingestion failed for document %s", document_id)
        await (
            db.table("documents")
            .update({"status": "failed", "error": str(exc)[:500]})
            .eq("id", document_id)
            .execute()
        )
