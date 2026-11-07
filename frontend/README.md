# Studeasy frontend

React + Vite + TypeScript UI that exercises every backend feature end to end, with a
minimal pastel pixel-art theme (Pixelify Sans + Press Start 2P, notched pixel outlines,
8×8 SVG icons in `src/components/PixelIcon.tsx`, light and dark mode).

## What's covered

| Tab / screen | Backend endpoints |
|---|---|
| Sign in / sign up | Supabase Auth (supabase-js) |
| Courses | `GET/POST /api/courses`, `DELETE /api/courses/{id}` |
| Material | upload (multipart), list with 2 s polling while `processing`, delete |
| Chat | `POST /chat` (SSE: intent, sources, token, verification, quiz, plan, error), `GET /chat/history` |
| Quiz | generate (topic, count, types), answer each question (MC / true-false / open) |
| Flashcards | generate, review due cards with SM-2 grades 0–5 |
| Planning | exams CRUD, mastery map, study plan (`daily_minutes`, `days`) |
| Settings (gear icon) | `GET /api/features`, `GET/PATCH /api/me/preferences` (reels opt-in) |
| Reels (only when the server has reels on **and** the student opted in) | `GET /reels/feed` with prefetch ~2 from the end, `POST /reels/{id}/view` (watch time) on swipe-away, `POST /reels/{id}/answer`, flashcard reels rated via SM-2 (Again 1 / Good 4 / Easy 5); explainer, quiz, flashcard, myth vs fact, mnemonic and break cards |

The header shows whether `GET /api/health` is reachable.

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
