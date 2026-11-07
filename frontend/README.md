# Studeasy frontend (draft)

A deliberately plain React + Vite + TypeScript UI whose only goal is to exercise every
backend feature end to end. Styling and structure are placeholders, to be redesigned later.

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
