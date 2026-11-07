import { useCallback, useEffect, useState } from "react";
import { api, call, type AnswerResult, type Quiz, type QuestionType, type QuizSummary } from "../api/client";
import { ErrorBox } from "../components/ErrorBox";
import { HistoryList } from "../components/HistoryList";
import { Loader } from "../components/Loader";
import { QuizView } from "../components/QuizView";
import { TopicPicker } from "../components/TopicPicker";
import { pct, timeAgo } from "../lib/format";
import type { ModeProps } from "./types";

const ALL_TYPES: { t: QuestionType; label: string }[] = [
  { t: "multiple_choice", label: "Multiple choice" },
  { t: "true_false", label: "True / false" },
  { t: "open", label: "Open answer" },
];

function NewQuiz({ courseId, hasMaterial, onCreated }: { courseId: string; hasMaterial: boolean; onCreated: (q: Quiz) => void }) {
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [types, setTypes] = useState<QuestionType[]>(["multiple_choice", "true_false", "open"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onCreated(await call(api.POST("/api/courses/{course_id}/quizzes", { params: { path: { course_id: courseId } }, body: { topic: topic || null, types, count } })));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (busy) return <Loader size="lg" label={`Writing ${count} question${count === 1 ? "" : "s"}${topic ? ` on ${topic}` : ""}…`} />;

  return (
    <form className="new-form" onSubmit={generate}>
      <h2>New quiz</h2>
      <p className="muted">Questions are written from your sources and every answer updates your mastery map.</p>
      {!hasMaterial && <p className="notice small">Add course material in Sources to generate a quiz.</p>}
      <TopicPicker courseId={courseId} value={topic} onChange={setTopic} />
      <div className="field">
        <span className="field-label">Question types</span>
        <div className="row wrap">
          {ALL_TYPES.map(({ t, label }) => (
            <label key={t} className="check">
              <input type="checkbox" checked={types.includes(t)} onChange={(e) => setTypes((ts) => (e.target.checked ? [...ts, t] : ts.filter((x) => x !== t)))} />
              {label}
            </label>
          ))}
        </div>
      </div>
      <div className="field">
        <label className="field-label" htmlFor="count">Questions: {count}</label>
        <input id="count" type="range" min={1} max={20} value={count} onChange={(e) => setCount(+e.target.value)} />
      </div>
      <ErrorBox error={error} />
      <button type="submit" disabled={busy || types.length === 0 || !hasMaterial}>{busy ? "Writing questions…" : "Generate quiz"}</button>
    </form>
  );
}

function OpenQuiz({ id, summary, onAnswered, onDelete }: { id: string; summary?: QuizSummary; onAnswered: (r: AnswerResult) => void; onDelete: () => void }) {
  const [data, setData] = useState<{ quiz: Quiz; answers: AnswerResult[] } | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    Promise.all([
      call(api.GET("/api/quizzes/{quiz_id}", { params: { path: { quiz_id: id } } })),
      call(api.GET("/api/quizzes/{quiz_id}/answers", { params: { path: { quiz_id: id } } })),
    ])
      .then(([quiz, answers]) => !cancelled && setData({ quiz, answers }))
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <ErrorBox error={error} />;
  if (!data) return <Loader quick label="Loading quiz…" />;
  const total = data.quiz.questions.length;
  const answered = summary?.answered_count ?? data.answers.length;

  return (
    <div>
      <div className="main-head">
        <div>
          <h2>{data.quiz.topic || "Whole course"}</h2>
          <p className="muted small">
            {total} questions · {timeAgo(data.quiz.created_at)}
            {summary?.score != null && <> · score {pct(summary.score)}</>}
          </p>
        </div>
        <button className="danger small" onClick={() => confirm("Delete this quiz?") && onDelete()}>Delete</button>
      </div>
      <div className="progress" title={`${answered}/${total} answered`}>
        <div style={{ width: `${total ? (answered / total) * 100 : 0}%` }} />
      </div>
      <QuizView quiz={data.quiz} initial={data.answers} onAnswered={onAnswered} compact={false} />
      {answered === total && total > 0 && <p className="notice center">Quiz complete! Start a new one from the left, or ask the tutor about what you missed.</p>}
    </div>
  );
}

export function QuizMode({ courseId, hasMaterial, item, onItem }: ModeProps) {
  const [quizzes, setQuizzes] = useState<QuizSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<string | null>(item);
  // Keep the open item in the URL (?item=) so a refresh reopens it.
  useEffect(() => {
    if (active !== item) onItem(active);
  }, [active, item, onItem]);

  const load = useCallback(async () => {
    try {
      const qs = await call(api.GET("/api/courses/{course_id}/quizzes", { params: { path: { course_id: courseId } } }));
      setQuizzes(qs);
      setActive((a) => (a && !qs.some((q) => q.id === a) ? null : a));
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  async function remove(id: string) {
    await call(api.DELETE("/api/quizzes/{quiz_id}", { params: { path: { quiz_id: id } } }));
    setQuizzes((qs) => qs.filter((q) => q.id !== id));
    if (active === id) setActive(null);
  }

  return (
    <>
      <HistoryList
        title="Quizzes"
        icon="quiz"
        newLabel="New quiz"
        newActive={active === null}
        onNew={() => setActive(null)}
        items={quizzes.map((q) => ({
          id: q.id,
          title: q.topic || "Whole course",
          subtitle: `${timeAgo(q.created_at)} · ${q.answered_count}/${q.question_count}`,
          badge: q.score != null ? <span className={`score ${q.score >= 0.6 ? "ok" : "bad"}`}>{pct(q.score)}</span> : undefined,
        }))}
        selectedId={active}
        onSelect={setActive}
        onDelete={(id) => remove(id).catch(() => {})}
        loading={loading}
        empty="Quizzes you create (here or in chat) appear here."
      />
      <section className="ws-main">
        {active ? (
          <OpenQuiz
            key={active}
            id={active}
            summary={quizzes.find((q) => q.id === active)}
            onAnswered={() => load().catch(() => {})}
            onDelete={() => remove(active).catch(() => {})}
          />
        ) : (
          <NewQuiz
            courseId={courseId}
            hasMaterial={hasMaterial}
            onCreated={(q) => {
              setQuizzes((qs) => [{ id: q.id, topic: q.topic, created_at: q.created_at, question_count: q.questions.length, answered_count: 0, score: null }, ...qs]);
              setActive(q.id);
            }}
          />
        )}
      </section>
    </>
  );
}
