import { useState } from "react";
import { api, call, type Quiz, type QuestionType } from "../api/client";
import { ErrorBox } from "./ErrorBox";
import { QuizView } from "./QuizView";

const ALL_TYPES: QuestionType[] = ["multiple_choice", "true_false", "open"];

export function Quizzes({ courseId }: { courseId: string }) {
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [types, setTypes] = useState<QuestionType[]>(ALL_TYPES);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setQuiz(null);
    try {
      setQuiz(
        await call(
          api.POST("/api/courses/{course_id}/quizzes", {
            params: { path: { course_id: courseId } },
            body: { topic: topic || null, types, count },
          }),
        ),
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h3>Generate a quiz</h3>
      <form onSubmit={generate} className="row wrap">
        <input placeholder="Topic (optional)" value={topic} onChange={(e) => setTopic(e.target.value)} />
        <label>
          Questions{" "}
          <input type="number" min={1} max={20} value={count} onChange={(e) => setCount(+e.target.value)} className="num" />
        </label>
        {ALL_TYPES.map((t) => (
          <label key={t}>
            <input
              type="checkbox"
              checked={types.includes(t)}
              onChange={(e) => setTypes((ts) => (e.target.checked ? [...ts, t] : ts.filter((x) => x !== t)))}
            />{" "}
            {t.replace("_", " ")}
          </label>
        ))}
        <button type="submit" disabled={busy || types.length === 0}>{busy ? "Generating…" : "Generate"}</button>
      </form>
      <ErrorBox error={error} />
      {quiz && <QuizView quiz={quiz} />}
    </div>
  );
}
