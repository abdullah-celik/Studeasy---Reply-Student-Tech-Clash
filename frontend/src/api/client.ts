import createClient from "openapi-fetch";
import { createClient as createSupabase } from "@supabase/supabase-js";
import type { paths, components } from "./schema";

export const supabase = createSupabase(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY, // anon key only — never the service role key
);

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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

type S = components["schemas"];
export type Course = S["Course"];
export type Document = S["Document"];
export type Quiz = S["Quiz"];
export type AnswerResult = S["AnswerResult"];
export type Flashcard = S["Flashcard"];
export type Exam = S["Exam"];
export type MasteryItem = S["MasteryItem"];
export type StudyPlan = S["StudyPlan"];
// Only used in SSE chat events, so not in the OpenAPI spec (mirrors backend app/schemas.py Source).
export type Source = { index: number; filename: string; location: string; snippet: string };
export type ChatMessage = S["ChatMessage"];
export type QuestionType = S["QuizCreate"]["types"] extends (infer T)[] | undefined ? T : never;

/** Turn a FastAPI error body ({detail: string | ValidationError[]}) into a readable message. */
export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  const detail = (err as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg ?? JSON.stringify(d)).join("; ");
  return JSON.stringify(err);
}

/** Unwrap an openapi-fetch result, throwing a readable Error on failure. */
export async function call<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (error !== undefined || !response.ok) {
    throw new ApiError(response.status, `${response.status}: ${errorMessage(error)}`);
  }
  return data as T;
}

export type Features = S["Features"];
export type Preferences = S["Preferences"];
export type ReelFeed = S["ReelFeed"];
export type Reel = ReelFeed["items"][number];
export type ReelAnswerResult = S["ReelAnswerResult"];

/** Error carrying the HTTP status, so screens can react to 403 / 409 specifically. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
