import { fetchEventSource } from "@microsoft/fetch-event-source";
import { API_URL, authHeader, type Quiz, type Source, type StudyPlan } from "./client";

// SSE events are not in the OpenAPI spec; this union is the contract (backend/docs/FRONTEND.md).
export type ChatEvent =
  | { event: "intent"; data: { intent: "explain" | "quiz" | "plan" | "chitchat"; topic: string | null } }
  | { event: "sources"; data: { sources: Source[] } }
  | { event: "token"; data: { text: string } }
  | { event: "verification"; data: { grounded: boolean; unsupported_claims: string[] } }
  | { event: "quiz"; data: Quiz }
  | { event: "plan"; data: StudyPlan }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: Record<string, never> };

export async function sendChat(
  courseId: string,
  message: string,
  onEvent: (e: ChatEvent) => void,
  chatId?: string,
) {
  const ctrl = new AbortController();
  await fetchEventSource(`${API_URL}/api/courses/${courseId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify(chatId ? { message, chat_id: chatId } : { message }),
    signal: ctrl.signal,
    openWhenHidden: true,
    async onopen(res) {
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    },
    onmessage(msg) {
      if (!msg.event) return; // keep-alive pings
      onEvent({ event: msg.event, data: JSON.parse(msg.data) } as ChatEvent);
      if (msg.event === "done") ctrl.abort();
    },
    onclose() {
      ctrl.abort();
    },
    onerror(err) {
      throw err; // don't auto-retry a chat message
    },
  });
}
