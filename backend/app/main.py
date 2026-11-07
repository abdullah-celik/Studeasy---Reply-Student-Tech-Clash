import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.config import get_settings
from app.db import init_supabase
from app.errors import NoMaterialError
from app.routers import chat, courses, flashcards, planning, quizzes

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_supabase()
    yield


def _operation_id(route: APIRoute) -> str:
    """Readable operationIds (e.g. 'quizzes-create_quiz') for the generated TS client."""
    return f"{route.tags[0]}-{route.name}" if route.tags else route.name


app = FastAPI(
    title="Studeasy API",
    version="0.1.0",
    description="Multi-agent study assistant: tutor, quiz master, planner and content agents.",
    lifespan=lifespan,
    generate_unique_id_function=_operation_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NoMaterialError)
async def no_material_handler(_: Request, exc: NoMaterialError):
    return JSONResponse(status_code=409, content={"detail": exc.message})


@app.get("/api/health", tags=["meta"])
async def health():
    return {"status": "ok"}


for r in (courses.router, chat.router, quizzes.router, flashcards.router, planning.router):
    app.include_router(r, prefix="/api")
