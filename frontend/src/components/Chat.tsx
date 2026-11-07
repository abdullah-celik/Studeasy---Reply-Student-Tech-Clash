import { useEffect, useRef, useState } from "react";
import { api, call, type Quiz, type Source, type StudyPlan } from "../api/client";
import { sendChat, type ChatEvent } from "../api/chat";
import { ErrorBox } from "./ErrorBox";
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
  explain: "Tutor is thinking…",
  quiz: "Building your quiz…",
  plan: "Planning your study days…",
  chitchat: "Thinking…",
};

export function Chat({ courseId }: { courseId: string }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    call(
      api.GET("/api/courses/{course_id}/chat/history", { params: { path: { course_id: courseId } } }),
    )
      .then((rows) => setMessages(rows.map((r) => ({ role: r.role, text: r.content }))))
      .catch(setError);
  }, [courseId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
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
        return patchLast((m) => ({ ...m, quiz: e.data }));
      case "plan":
        return patchLast((m) => ({ ...m, plan: e.data }));
      case "error":
        return patchLast((m) => ({ ...m, error: e.data.message }));
    }
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    setError(null);
    setBusy(true);
    setMessages((ms) => [...ms, { role: "user", text }, { role: "assistant", text: "" }]);
    try {
      await sendChat(courseId, text, onEvent);
    } catch (err) {
      patchLast((m) => ({ ...m, error: err instanceof Error ? err.message : String(err) }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat">
      <ErrorBox error={error} />
      <div className="messages">
        {messages.length === 0 && (
          <p className="muted">
            Try: “Explain photosynthesis”, “Quiz me on chapter 2”, or “Make me a study plan”.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.role === "assistant" && m.intent && <div className="muted small">intent: {m.intent}</div>}
            {m.text && <div className="text">{m.text}</div>}
            {m.role === "assistant" && busy && i === messages.length - 1 && !m.text && !m.quiz && !m.plan && !m.error && (
              <div className="muted">{WORKING[m.intent ?? ""] ?? "Thinking…"}</div>
            )}
            {m.sources && m.sources.length > 0 && (
              <div className="sources">
                {m.sources.map((s) => (
                  <span key={s.index} className="chip" title={s.snippet}>
                    [{s.index}] {s.filename} · {s.location}
                  </span>
                ))}
              </div>
            )}
            {m.verification &&
              (m.verification.grounded ? (
                <div className="result ok small">✓ Grounded in your notes</div>
              ) : (
                <div className="result bad small">
                  ⚠ Some claims may not be supported by your notes:
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
      <form onSubmit={send} className="row">
        <input
          placeholder="Ask the tutor, ask for a quiz, or ask for a plan…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>Send</button>
      </form>
    </div>
  );
}
