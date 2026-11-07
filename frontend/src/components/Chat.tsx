import { useEffect, useRef, useState } from "react";
import { api, call, type Quiz, type Source, type StudyPlan } from "../api/client";
import { sendChat, type ChatEvent } from "../api/chat";
import { ErrorBox } from "./ErrorBox";
import { PixelIcon } from "./PixelIcon";
import { PlanView } from "./PlanView";
import { QuizView } from "./QuizView";

type Msg = {
  role: "user" | "assistant";
  text: string;
  intent?: string;
  sources?: Source[];
  verification?: { grounded: boolean; unsupported_claims: string[] };
  quiz?: Quiz;
  plan?: StudyPlan;
  error?: string;
};

const WORKING: Record<string, string> = {
  explain: "Tutor is reading your notes…",
  quiz: "Quiz master is writing questions…",
  plan: "Planner is laying out your days…",
  chitchat: "Thinking…",
};

const SUGGESTIONS = [
  "Explain the key idea of the first chapter",
  "Quiz me on the hardest topic",
  "Make me a study plan for this week",
  "What should I review today?",
];

export function Chat({
  courseId,
  chatId,
  ensureChat,
  onActivity,
  onCite,
  hasMaterial,
}: {
  courseId: string;
  chatId: string | null;
  /** Creates the thread on the first message of a new chat and returns its id (null: no threads). */
  ensureChat: () => Promise<string | null>;
  /** Something changed that the sidebars care about (title, quiz or plan created). */
  onActivity: (what: "message" | "quiz" | "plan") => void;
  onCite: (filename: string) => void;
  hasMaterial: boolean;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const createdHere = useRef<string | null>(null); // don't reload history for a chat we just created mid-stream
  const sending = useRef(false);

  useEffect(() => {
    setError(null);
    if (!chatId) {
      setMessages([]);
      inputRef.current?.focus();
      return;
    }
    if (sending.current || createdHere.current === chatId) return;
    let cancelled = false;
    call(api.GET("/api/courses/{course_id}/chat/history", { params: { path: { course_id: courseId }, query: { chat_id: chatId, limit: 200 } } }))
      .then((rows) => !cancelled && setMessages(rows.map((r) => ({ role: r.role, text: r.content }))))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [courseId, chatId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  function patchLast(fn: (m: Msg) => Msg) {
    setMessages((ms) => [...ms.slice(0, -1), fn(ms[ms.length - 1])]);
  }

  function onEvent(e: ChatEvent) {
    switch (e.event) {
      case "intent":
        return patchLast((m) => ({ ...m, intent: e.data.intent }));
      case "sources":
        return patchLast((m) => ({ ...m, sources: e.data.sources }));
      case "token":
        return patchLast((m) => ({ ...m, text: m.text + e.data.text }));
      case "verification":
        return patchLast((m) => ({ ...m, verification: e.data }));
      case "quiz":
        onActivity("quiz");
        return patchLast((m) => ({ ...m, quiz: e.data }));
      case "plan":
        onActivity("plan");
        return patchLast((m) => ({ ...m, plan: e.data }));
      case "error":
        return patchLast((m) => ({ ...m, error: e.data.message }));
    }
  }

  async function send(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setBusy(true);
    sending.current = true;
    setMessages((ms) => [...ms, { role: "user", text }, { role: "assistant", text: "" }]);
    try {
      let id = chatId;
      if (!id) {
        id = await ensureChat();
        createdHere.current = id;
      }
      await sendChat(courseId, text, onEvent, id ?? undefined);
      onActivity("message");
    } catch (err) {
      patchLast((m) => ({ ...m, error: err instanceof Error ? err.message : String(err) }));
    } finally {
      sending.current = false;
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  const last = messages.length - 1;

  return (
    <div className="chat">
      <ErrorBox error={error} />
      <div className="messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <PixelIcon name="chat" size={40} />
            <h2>What do you want to learn?</h2>
            <p className="muted">
              Ask for an explanation, a quiz or a study plan. Answers are grounded in your course sources.
            </p>
            {!hasMaterial && <p className="notice small">Add some course material to Sources first, so the tutor has something to read.</p>}
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="secondary small" disabled={busy} onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.role === "assistant" && busy && i === last && !m.text && !m.quiz && !m.plan && !m.error && (
              <div className="muted typing">{WORKING[m.intent ?? ""] ?? "Thinking…"}</div>
            )}
            {m.text && <div className="text">{m.text}</div>}
            {m.sources && m.sources.length > 0 && (
              <div className="sources">
                {m.sources.map((s) => (
                  <button key={s.index} className="chip" title={s.snippet} onClick={() => onCite(s.filename)}>
                    [{s.index}] {s.filename} · {s.location}
                  </button>
                ))}
              </div>
            )}
            {m.verification &&
              (m.verification.grounded ? (
                <div className="verify ok small">✓ Grounded in your notes</div>
              ) : (
                <div className="verify bad small">
                  Some claims may not be in your notes:
                  <ul>{m.verification.unsupported_claims.map((c, j) => <li key={j}>{c}</li>)}</ul>
                </div>
              ))}
            {m.quiz && <QuizView quiz={m.quiz} />}
            {m.plan && <PlanView plan={m.plan} />}
            {m.error && <p className="error">{m.error}</p>}
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <textarea
          ref={inputRef}
          rows={1}
          placeholder="Ask anything about this course…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>Send</button>
      </form>
    </div>
  );
}
