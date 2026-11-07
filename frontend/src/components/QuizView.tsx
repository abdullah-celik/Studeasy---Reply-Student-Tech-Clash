import { useState } from "react";
import { api, call, type AnswerResult, type Quiz } from "../api/client";
import { ErrorBox } from "./ErrorBox";
import { Loader } from "./Loader";

type Question = Quiz["questions"][number];

function QuestionCard({
  quizId,
  q,
  n,
  initial,
  onAnswered,
}: {
  quizId: string;
  q: Question;
  n: number;
  initial?: AnswerResult;
  onAnswered?: (r: AnswerResult) => void;
}) {
  const [response, setResponse] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(initial ?? null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(value = response) {
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      const r = await call(
        api.POST("/api/quizzes/{quiz_id}/answers", {
          params: { path: { quiz_id: quizId } },
          body: { question_id: q.id, response: value },
        }),
      );
      setResult(r);
      onAnswered?.(r);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const choices = q.type === "true_false" && q.options.length === 0 ? ["True", "False"] : q.options;

  return (
    <div className="question">
      <div className="muted small">
        Q{n} · {q.type.replace("_", " ")} · {q.concept}
      </div>
      <p><strong>{q.prompt}</strong></p>
      {q.type === "open" ? (
        <div className="row">
          <textarea value={response} onChange={(e) => setResponse(e.target.value)} disabled={!!result} rows={3} />
          <button onClick={() => submit()} disabled={busy || !!result || !response}>
            {busy ? "Grading…" : "Submit"}
          </button>
        </div>
      ) : (
        <div className="options">
          {choices.map((opt) => (
            <label key={opt} className={response === opt ? "selected" : ""}>
              <input
                type="radio"
                name={q.id}
                value={opt}
                checked={response === opt}
                disabled={!!result || busy}
                onChange={() => {
                  setResponse(opt);
                  submit(opt);
                }}
              />
              {opt}
            </label>
          ))}
        </div>
      )}
      {busy && <Loader inline size="sm" label={q.type === "open" ? "Grading your answer…" : "Checking…"} />}
      <ErrorBox error={error} />
      {result && (
        <div className={`result ${result.correct ? "ok" : "bad"}`}>
          <strong>{result.correct ? "✓ Correct" : "✗ Not quite"}</strong> (score {Math.round(result.score * 100)}%)
          <div>{result.feedback}</div>
          <div className="small">Answer: {result.correct_answer}</div>
          <div className="small muted">{result.explanation}</div>
        </div>
      )}
    </div>
  );
}

export function QuizView({
  quiz,
  initial,
  onAnswered,
  compact = true,
}: {
  quiz: Quiz;
  initial?: AnswerResult[];
  onAnswered?: (r: AnswerResult) => void;
  /** Inline in chat: show a small heading. The Quiz tab renders its own header. */
  compact?: boolean;
}) {
  const byQ = new Map((initial ?? []).map((r) => [r.question_id, r]));
  return (
    <div className="quiz">
      {compact && <h4>Quiz{quiz.topic ? `: ${quiz.topic}` : ""} ({quiz.questions.length} questions)</h4>}
      {quiz.questions.map((q, i) => (
        <QuestionCard key={q.id} quizId={quiz.id} q={q} n={i + 1} initial={byQ.get(q.id)} onAnswered={onAnswered} />
      ))}
    </div>
  );
}
