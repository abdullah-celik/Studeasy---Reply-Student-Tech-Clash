import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from postgrest.exceptions import APIError

from app.config import get_settings
from app.db import get_db, init_supabase
from app.errors import NoMaterialError
from app.routers import chat, courses, flashcards, me, planning, quizzes, reels
from app.services.reembed import backfill_embeddings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = await init_supabase()
    # Re-embed chunks left without a vector after an AI-provider switch (runs in the background).
    task = asyncio.create_task(_backfill(db))
    yield
    task.cancel()


async def _backfill(db) -> None:
    try:
        await backfill_embeddings(db)
    except Exception:
        logging.getLogger("app.reembed").exception("Embedding backfill stopped")


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
    allow_origin_regex=get_settings().cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NoMaterialError)
async def no_material_handler(_: Request, exc: NoMaterialError):
    return JSONResponse(status_code=409, content={"detail": exc.message})


@app.exception_handler(APIError)
async def database_error_handler(_: Request, exc: APIError):
    # Handled here (inside the CORS middleware) so the browser sees a real error
    # instead of an opaque "Failed to fetch".
    logging.getLogger("app.db").error("Supabase error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "Database request failed. Please try again."})


@app.get("/api/health", tags=["meta"])
async def health():
    # A tiny database read on every health check (the keep-warm ping calls this every
    # 10 minutes) also counts as activity, so the free Supabase project is not paused.
    try:
        await get_db().table("courses").select("id").limit(1).execute()
        database = "ok"
    except Exception:
        database = "unreachable"
    return {"status": "ok", "database": database}


routers = [courses.router, chat.router, chat.threads, quizzes.router, flashcards.router, planning.router, me.router]
if get_settings().enable_reels:  # optional module
    routers.append(reels.router)
for r in routers:
    app.include_router(r, prefix="/api")
