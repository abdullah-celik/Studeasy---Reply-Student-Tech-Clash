# Studeasy backend (first draft)

A multi-agent study assistant. Students upload their own course material; a team of
agents turns it into a personal study loop:

```
upload notes ─► Content agent ─► knowledge base + concept list
                                       │
student ─► Orchestrator ─┬─► Tutor (+ Verifier) ── explains, grounded in their notes
                         ├─► Quiz master ──────── tests, grades ─┐
                         └─► Planner ──────────── schedules ◄────┤
                                                                  ▼
                                               Mastery map (score per concept)
```

The **mastery map** is what makes the agents work as a system: every quiz answer and
flashcard review updates a 0–1 score per concept, the planner prioritises the weakest
concepts, and the quiz master reuses the same concept names.

## Decisions taken (and why)

| Area | Choice | Notes |
|---|---|---|
| Language / framework | Python + FastAPI | Best AI ecosystem; OpenAPI spec → generated TypeScript types for the frontend |
| LLM | Mistral Small (`MISTRAL_CHAT_MODEL`, default `mistral-small-latest`) on the free Experiment plan; or OpenAI GPT-6 Luna with `LLM_PROVIDER=openai` | All Mistral calls share one throttle (`MISTRAL_REQUESTS_PER_SECOND`, 0.9) because the free plan allows about 1 request/second |
| Embeddings | `mistral-embed`, 1024 dims (OpenAI: `text-embedding-3-small`, 1536) | The size is hard-coded in `supabase/schema.sql`; after a provider switch the backend re-embeds existing chunks on startup |
| Agent orchestration | LangGraph | One explicit graph (`app/agents/graph.py`), easy to demo and debug |
| Database / vectors | Supabase Postgres + pgvector | HNSW cosine index, `match_chunks` SQL function |
| Auth | Supabase Auth | Frontend logs in with supabase-js, sends `Authorization: Bearer <access_token>` |
| Streaming | Server-Sent Events | `POST /chat` streams `token`, `sources`, `verification`, … events |
| File types | PDF, PPTX (incl. speaker notes), DOCX, TXT, MD | Scanned PDFs (no text layer) fail; no OCR yet |
| Original files | **Not stored** | Parsed → chunked → embedded → discarded |
| Quiz types | Multiple choice, true/false, open (LLM-graded), flashcards | Malformed LLM questions are dropped, not shown |
| Spaced repetition | SM-2 | `app/services/sm2.py`, unit-tested |
| Tooling | `uv` (pyproject.toml) **and** pip (requirements*.txt) | Keep both dependency lists in sync |
| Docker | Dockerfile for the API only | Supabase is hosted, so no compose file needed |
| **Reels (optional)** | Animated text cards: explainer, quiz, flashcard flip, myth vs fact / mnemonic | `ENABLE_REELS` server switch **and** per-student opt-in |
| Reels feed | Adaptive, generated on demand | Weakest concept + one random concept per batch; due flashcards slotted in |
| Reels wellbeing | Soft "take a break" card every `REELS_BREAK_EVERY` reels | Student can keep scrolling |
| Reels signals | Views + watch time | Seen reels never repeat |

Smaller choices I made without asking (easy to change, please confirm):

1. **Backend uses the service-role key** and filters every query by `user_id` itself.
   RLS is still enabled on every table, so the frontend *may* read tables directly with
   supabase-js if you want (e.g. realtime document status).
2. **Token verification calls Supabase Auth** (`auth.get_user`) on each request: simple and works
   with any signing key, but costs one HTTP round-trip. Can switch to local JWKS verification later.
3. **Uploads are processed in a background task**: the upload returns `202` with
   `status: "processing"`; the frontend polls `GET /documents`.
4. **Verifier agent runs after the tutor** and emits a `verification` event (grounded yes/no +
   unsupported claims). Toggle with `VERIFY_ANSWERS`.
5. **Tutor is Socratic** for exercise-like questions (hint first), direct for "explain X",
   answers in the student's language, cites sources as `[1]`.
6. **Mastery score** = moving average (newest result weighs 30%). Flashcard grade 0–5 → 0–1.
7. **Plans** cover the days until the next exam (max 14, default 7), ~60 min/day.
8. **Chat memory** = last 10 messages per course.
9. All routes are under **`/api`**; operationIds look like `quizzes-create_quiz`.
10. **Reels are opt-in per student** (`reels_enabled` defaults to `false`), so the module
    stays an option. Flip into it with `PATCH /api/me/preferences`.
11. Each reel batch makes one LLM call per concept (run in parallel), ~4 cards each.
    Flashcard reels are real deck cards, so rating them updates SM-2; quiz reels update mastery.

## Project layout

```
app/
  main.py            FastAPI app, CORS, routers
  config.py          settings from env
  deps.py            auth (Supabase JWT) + course ownership check
  llm.py             Mistral or OpenAI chat / structured output / embeddings
  schemas.py         API contract (→ OpenAPI → TypeScript)
  agents/
    graph.py         LangGraph: orchestrator → tutor/verifier | quiz master | planner
    orchestrator.py  intent + topic classification
    tutor.py         Socratic, grounded answers
    verifier.py      checks answers against sources
    quiz.py          questions, flashcards, open-answer grading
    planner.py       day-by-day study plan
    content.py       key-concept extraction at upload
    reels.py         turns a concept into swipeable cards
  services/          ingestion, retrieval, mastery, SM-2, quizzes, planning, chat history
  routers/           courses+documents, chat (SSE), quizzes, flashcards, planning
supabase/schema.sql  tables, RLS, pgvector index, match_chunks()
tests/               SM-2, parsing, planning, quiz cleaning
docs/FRONTEND.md     how the TypeScript frontend talks to this API
```

## API overview

| Method | Path | What it does |
|---|---|---|
| POST/GET | `/api/courses` | create / list courses |
| GET/DELETE | `/api/courses/{id}` | get / delete a course (cascades) |
| POST | `/api/courses/{id}/documents` | upload files (multipart `files`) → background ingestion |
| GET | `/api/courses/{id}/documents` | list documents + processing status |
| DELETE | `/api/courses/{id}/documents/{doc_id}` | remove a document and its chunks |
| POST | `/api/courses/{id}/chat` | **SSE** — talk to the agents |
| GET | `/api/courses/{id}/chat/history` | past messages |
| POST | `/api/courses/{id}/quizzes` | generate a quiz (`topic?`, `types`, `count`) |
| GET | `/api/quizzes/{quiz_id}` | quiz without answers |
| POST | `/api/quizzes/{quiz_id}/answers` | grade one answer, update mastery |
| POST | `/api/courses/{id}/flashcards` | generate flashcards |
| GET | `/api/courses/{id}/flashcards/due` | cards due for review |
| POST | `/api/flashcards/{card_id}/review` | SM-2 review (`quality` 0–5) |
| POST/GET/DELETE | `/api/courses/{id}/exams` | manage exam dates |
| GET | `/api/courses/{id}/mastery` | mastery map (weakest first) |
| GET | `/api/courses/{id}/plan` | study plan (`daily_minutes`, `days`) |
| GET | `/api/features` | optional modules enabled on this server (no auth) |
| GET/PATCH | `/api/me/preferences` | student switches, e.g. `reels_enabled` |
| GET | `/api/courses/{id}/reels/feed` | **reels** — next page of unseen reels (generates more on demand) |
| POST | `/api/reels/{id}/view` | mark seen + watch time |
| POST | `/api/reels/{id}/answer` | answer a quiz reel |
| GET | `/api/courses/{id}/reels/history` | reels already viewed (newest first) |
| GET/POST | `/api/courses/{id}/chats` | list / create chat threads (several chats per course) |
| PATCH/DELETE | `/api/chats/{chat_id}` | rename / delete a thread |
| GET | `/api/courses/{id}/quizzes` | quiz history with progress (`answered_count`, `score`) |
| GET | `/api/quizzes/{quiz_id}/answers` | latest result per answered question (restore a quiz) |
| DELETE | `/api/quizzes/{quiz_id}` | delete a quiz |
| GET | `/api/courses/{id}/flashcards/decks` | flashcard decks (one per generation) with due counts |
| GET/DELETE | `/api/flashcards/decks/{deck_id}` | cards of a deck / delete a deck |
| POST/GET | `/api/courses/{id}/plans` | make **and save** a plan / list saved plans |
| DELETE | `/api/courses/{id}/plans/{plan_id}` | delete a saved plan |

History endpoints are additive: `POST /chat` takes an optional `chat_id` (messages without one
keep the old single-thread behaviour), `GET /chat/history` takes an optional `chat_id`, and
`GET /plan` is still stateless. Plans the planner makes from chat are saved too. Re-run
`supabase/schema.sql` to add the `chats`, `flashcard_decks` and `study_plans` tables.

Interactive docs: http://localhost:8000/docs

## Setup

1. Create a Supabase project, open the SQL editor and run `supabase/schema.sql`.
   The script is idempotent: after pulling new features (like reels), just run it again.
2. `cp .env.example .env` and fill in the Mistral key, Supabase URL and **service role** key.
3. Install and run:

```bash
# with uv
uv sync
uv run uvicorn app.main:app --reload

# or with pip
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Tests and lint: `pytest` and `ruff check .` (or prefix with `uv run`).

Docker: `docker build -t studeasy-api . && docker run --env-file .env -p 8000:8000 studeasy-api`

## Known gaps / next decisions

- No OCR for scanned PDFs; DOCX tables are ignored.
- Ingestion runs in-process; a crash mid-upload leaves the document in `processing`.
  For production, move it to a queue (e.g. Supabase Edge Functions, Celery, or arq).
- No rate limiting on LLM endpoints yet.
- No `uv.lock` committed yet — run `uv sync` once and commit the lockfile.
