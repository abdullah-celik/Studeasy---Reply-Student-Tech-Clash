# Studeasy frontend

React + Vite + TypeScript UI that exercises every backend feature end to end, with a
minimal pastel pixel-art theme (Pixelify Sans + Press Start 2P, notched pixel outlines,
8×8 SVG icons in `src/components/PixelIcon.tsx`, light and dark mode).

## Layout

- **Dashboard**: one panel per course, plus a "New course" panel (a new course opens straight away).
- **Course workspace**: three columns.
  - **Left — history of the current mode only**: chats, quizzes, flashcard decks, seen reels or
    saved plans, each with a "New …" button; items can be reopened and deleted (chats renamed too).
  - **Centre — the mode**: Chat (default), Quiz, Flashcards, Reels, Plan.
  - **Right — Sources**, shared by every mode: drag-and-drop upload, processing status, delete.
    Citation chips in chat flash the cited file here.
  - Below 1180px Sources becomes a drawer, below 820px History too (toggle buttons in the bar).
- The last mode is remembered per course.

| Mode | Backend endpoints |
|---|---|
| Chat | `GET/POST /courses/{id}/chats`, `PATCH/DELETE /chats/{id}`, `POST /chat` (SSE, with `chat_id`), `GET /chat/history?chat_id=` |
| Quiz | `GET/POST /courses/{id}/quizzes`, `GET /quizzes/{id}`, `GET/POST /quizzes/{id}/answers`, `DELETE /quizzes/{id}` |
| Flashcards | `POST /courses/{id}/flashcards`, `GET /flashcards/decks…`, `GET /flashcards/due`, `POST /flashcards/{id}/review` |
| Reels | `GET /reels/feed`, `GET /reels/history`, `POST /reels/{id}/view`, `POST /reels/{id}/answer`, opt-in via `PATCH /me/preferences` |
| Plan | `GET/POST/DELETE /courses/{id}/exams`, `GET /mastery`, `GET/POST /courses/{id}/plans`, `DELETE /plans/{id}` |
| Sources | `GET/POST/DELETE /courses/{id}/documents` (polls every 2 s while processing) |

Settings (gear icon) holds the reels switch. The header shows whether `GET /api/health` answers.

## Run

```bash
cp .env.example .env   # fill in Supabase URL + anon key
npm install
npm run dev            # http://localhost:5173 (already in the backend's default CORS_ORIGINS)
```

Start the backend first (see `../backend/README.md`).

## API types

`src/api/schema.d.ts` is generated from the backend's OpenAPI spec. Regenerate after backend
changes (backend must be running):

```bash
npm run gen:api
```

SSE chat events aren't in the spec; their types live in `src/api/chat.ts`.
