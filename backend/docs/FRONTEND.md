# Frontend integration (TypeScript)

The backend's Pydantic models are the contract. FastAPI publishes them at
`/openapi.json`, so the frontend **generates** its types instead of writing them by hand.

## 1. Generate types and a typed client

```bash
npm i openapi-fetch @supabase/supabase-js @microsoft/fetch-event-source
npm i -D openapi-typescript
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts
```

Add it as a script so it's re-run whenever the backend changes:

```json
"scripts": { "gen:api": "openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts" }
```

## 2. Auth + API client

```ts
// src/api/client.ts
import createClient from "openapi-fetch";
import { createClient as createSupabase } from "@supabase/supabase-js";
import type { paths, components } from "./schema";

export const supabase = createSupabase(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY, // anon key only — never the service role key
);

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const api = createClient<paths>({ baseUrl: API_URL });
api.use({
  async onRequest({ request }) {
    for (const [k, v] of Object.entries(await authHeader())) request.headers.set(k, v);
    return request;
  },
});

export type Course = components["schemas"]["Course"];
export type Quiz = components["schemas"]["Quiz"];
export type StudyPlan = components["schemas"]["StudyPlan"];
```

Usage is fully typed (paths, params and bodies are checked by the compiler):

```ts
const { data: courses } = await api.GET("/api/courses");
const { data: quiz } = await api.POST("/api/courses/{course_id}/quizzes", {
  params: { path: { course_id: courseId } },
  body: { topic: "photosynthesis", types: ["multiple_choice", "open"], count: 5 },
});
const { data: result } = await api.POST("/api/quizzes/{quiz_id}/answers", {
  params: { path: { quiz_id: quiz!.id } },
  body: { question_id: quiz!.questions[0].id, response: "Chlorophyll" },
});
```

## 3. Uploading material

`multipart/form-data` with field name `files` (one or many). Returns `202` with documents in
`status: "processing"`; poll `GET /api/courses/{id}/documents` every ~2 s until each is
`ready` or `failed` (`error` explains why).

```ts
const form = new FormData();
for (const f of fileInput.files!) form.append("files", f);
await fetch(`${API_URL}/api/courses/${courseId}/documents`, {
  method: "POST",
  headers: await authHeader(), // don't set Content-Type; the browser adds the boundary
  body: form,
});
```

## 4. Chat over Server-Sent Events

The native `EventSource` can't send POST bodies or auth headers, so use
`@microsoft/fetch-event-source`. SSE events are not in the OpenAPI spec; this union is the contract:

```ts
// src/api/chatEvents.ts
import type { components } from "./schema";

type Source = components["schemas"]["Source"];

export type ChatEvent =
  | { event: "intent"; data: { intent: "explain" | "quiz" | "plan" | "chitchat"; topic: string | null } }
  | { event: "sources"; data: { sources: Source[] } }
  | { event: "token"; data: { text: string } }
  | { event: "verification"; data: { grounded: boolean; unsupported_claims: string[] } }
  | { event: "quiz"; data: components["schemas"]["Quiz"] }
  | { event: "plan"; data: components["schemas"]["StudyPlan"] }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: Record<string, never> };
```

```ts
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { API_URL, authHeader } from "./client";
import type { ChatEvent } from "./chatEvents";

export async function sendChat(courseId: string, message: string, onEvent: (e: ChatEvent) => void) {
  const ctrl = new AbortController();
  await fetchEventSource(`${API_URL}/api/courses/${courseId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify({ message }),
    signal: ctrl.signal,
    openWhenHidden: true,
    onmessage(msg) {
      if (!msg.event) return; // keep-alive pings
      onEvent({ event: msg.event, data: JSON.parse(msg.data) } as ChatEvent);
      if (msg.event === "done") ctrl.abort();
    },
    onerror(err) {
      throw err; // don't auto-retry a chat message
    },
  });
}
```

Typical rendering per event:

| Event | UI |
|---|---|
| `intent` | show which agent is working ("Tutor is thinking…", "Building your quiz…") |
| `sources` | citation chips; `[n]` in the answer maps to `sources[n-1]` |
| `token` | append to the assistant bubble |
| `verification` | badge "✓ grounded in your notes" or a warning listing unsupported claims |
| `quiz` | render the quiz component inline (answers via `POST /api/quizzes/{id}/answers`) |
| `plan` | render the day-by-day plan |
| `error` | toast / inline message (e.g. "Upload course material first") |

## 5. Reels (optional module)

Two switches decide whether to show the Reels tab:

```ts
const { data: features } = await api.GET("/api/features");          // server switch
const { data: prefs } = await api.GET("/api/me/preferences");        // student switch
const showReelsTab = features?.reels && prefs?.reels_enabled;

// settings toggle
await api.PATCH("/api/me/preferences", { body: { reels_enabled: true } });
```

`ReelFeed.items` is a discriminated union on `type`, generated from OpenAPI:

```ts
type Reel = components["schemas"]["ReelFeed"]["items"][number];

function ReelCard({ reel }: { reel: Reel }) {
  switch (reel.type) {
    case "explainer":  /* reel.content.hook, .points[], .takeaway, .emoji */ break;
    case "quiz":       /* reel.content.question, .options[], .kind */ break;
    case "flashcard":  /* tap to flip: .front / .back; rate via /flashcards/{flashcard_id}/review */ break;
    case "myth_fact":  /* .myth, .fact, .why */ break;
    case "mnemonic":   /* .mnemonic, .explanation */ break;
    case "break":      /* wellbeing card: .title, .message, .reels_watched, .minutes, .concepts */ break;
  }
}
```

Feed loop (vertical full-screen swiper, e.g. Swiper.js or CSS scroll-snap):

1. `GET /api/courses/{id}/reels/feed` and render the items.
2. When the student is ~2 reels from the end, fetch the next page and append it. The first
   page after new material can take a few seconds because it's generated: show a skeleton card.
3. When a reel leaves the screen, `POST /api/reels/{id}/view` with `{ watch_ms, completed }`
   (skip for `break` cards, which have no `id`). Viewed reels never come back.
4. Quiz reel: `POST /api/reels/{id}/answer` with `{ response }` → `{ correct, correct_answer, explanation }`.
5. Flashcard reel: after the flip, offer 3 buttons mapped to SM-2 quality, e.g. Again = 1,
   Good = 4, Easy = 5, sent to `POST /api/flashcards/{flashcard_id}/review`.

`403` from the feed means the student has reels turned off; `409` means the course has no
material yet.

## 6. History (several chats, quizzes, decks and plans)

```ts
// Chats: create a thread, then pass its id with every message.
const { data: chat } = await api.POST("/api/courses/{course_id}/chats", { params: { path: { course_id } }, body: {} });
await sendChat(courseId, "Explain osmosis", onEvent, chat!.id);   // body: { message, chat_id }
await api.GET("/api/courses/{course_id}/chat/history", { params: { path: { course_id }, query: { chat_id: chat!.id } } });

await api.GET("/api/courses/{course_id}/quizzes", ...);           // QuizSummary[]
await api.GET("/api/quizzes/{quiz_id}/answers", ...);             // restore earlier answers
await api.GET("/api/courses/{course_id}/flashcards/decks", ...);  // FlashcardDeck[]
await api.POST("/api/courses/{course_id}/plans", { ..., body: { daily_minutes: 60 } });  // SavedPlan
```

A thread's title is set from its first message; rename it with `PATCH /api/chats/{chat_id}`.

## 7. Errors

Standard FastAPI shape: `{ "detail": string | ValidationError[] }`.
`401` → refresh the Supabase session or redirect to login; `409` → the course has no
material yet; `415` / `413` → unsupported or too-large upload.

## 8. CORS

Add the frontend origin to `CORS_ORIGINS` in the backend `.env`
(defaults: `http://localhost:5173` for Vite, `http://localhost:3000` for Next.js).
