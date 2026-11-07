from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status

from app.config import get_settings
from app.db import get_db
from app.deps import CurrentUser, get_current_user, get_owned_course
from app.schemas import Course, CourseCreate, Document
from app.services.ingestion import SUPPORTED_EXTENSIONS, process_document
from supabase import AsyncClient

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=Course, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    res = await db.table("courses").insert({"user_id": user.id, **body.model_dump()}).execute()
    return res.data[0]


@router.get("", response_model=list[Course])
async def list_courses(
    user: CurrentUser = Depends(get_current_user), db: AsyncClient = Depends(get_db)
):
    res = (
        await db.table("courses")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


@router.get("/{course_id}", response_model=Course)
async def get_course(course: dict = Depends(get_owned_course)):
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course: dict = Depends(get_owned_course), db: AsyncClient = Depends(get_db)):
    await db.table("courses").delete().eq("id", course["id"]).execute()


# Documents ------------------------------------------------------------------
@router.post(
    "/{course_id}/documents",
    response_model=list[Document],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload course material (PDF, PPTX, DOCX, TXT, MD)",
    description="Files are processed in the background. Poll GET /documents until "
    "status is 'ready' or 'failed'. Originals are not stored.",
)
async def upload_documents(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    course: dict = Depends(get_owned_course),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        name = f.filename or "upload"
        ext = Path(name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"{name}: unsupported type. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            )
        data = await f.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{name} exceeds the upload limit"
            )
        payloads.append((name, data))

    docs = []
    for name, data in payloads:
        doc = (
            await db.table("documents")
            .insert({"user_id": user.id, "course_id": course["id"], "filename": name})
            .execute()
        ).data[0]
        background.add_task(process_document, db, doc["id"], user.id, course["id"], name, data)
        docs.append(doc)
    return docs


@router.get("/{course_id}/documents", response_model=list[Document])
async def list_documents(course: dict = Depends(get_owned_course), db: AsyncClient = Depends(get_db)):
    res = (
        await db.table("documents")
        .select("*")
        .eq("course_id", course["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


@router.delete("/{course_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    course: dict = Depends(get_owned_course),
    db: AsyncClient = Depends(get_db),
):
    await (
        db.table("documents")
        .delete()
        .eq("id", str(document_id))
        .eq("course_id", course["id"])
        .execute()
    )
