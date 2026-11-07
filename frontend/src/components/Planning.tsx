import { useCallback, useEffect, useState } from "react";
import { api, call, type Exam, type MasteryItem, type StudyPlan } from "../api/client";
import { ErrorBox } from "./ErrorBox";
import { PlanView } from "./PlanView";

export function Planning({ courseId }: { courseId: string }) {
  const path = { course_id: courseId };
  const [exams, setExams] = useState<Exam[]>([]);
  const [mastery, setMastery] = useState<MasteryItem[]>([]);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState(60);
  const [days, setDays] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const p = { params: { path: { course_id: courseId } } };
      const [e, m] = await Promise.all([
        call(api.GET("/api/courses/{course_id}/exams", p)),
        call(api.GET("/api/courses/{course_id}/mastery", p)),
      ]);
      setExams(e);
      setMastery(m);
    } catch (e) {
      setError(e);
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  async function addExam(e: React.FormEvent) {
    e.preventDefault();
    try {
      await call(api.POST("/api/courses/{course_id}/exams", { params: { path }, body: { title, exam_date: date } }));
      setTitle("");
      setDate("");
      await load();
    } catch (e) {
      setError(e);
    }
  }

  async function removeExam(id: string) {
    try {
      await call(api.DELETE("/api/courses/{course_id}/exams/{exam_id}", { params: { path: { ...path, exam_id: id } } }));
      setExams((xs) => xs.filter((x) => x.id !== id));
    } catch (e) {
      setError(e);
    }
  }

  async function makePlan() {
    setBusy(true);
    setError(null);
    try {
      setPlan(
        await call(
          api.GET("/api/courses/{course_id}/plan", {
            params: { path, query: { daily_minutes: dailyMinutes, days: days ? +days : undefined } },
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
      <ErrorBox error={error} />
      <h3>Exams</h3>
      <form onSubmit={addExam} className="row">
        <input placeholder="Exam title" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        <button type="submit">Add exam</button>
      </form>
      <ul className="list">
        {exams.map((x) => (
          <li key={x.id}>
            <span>{x.title} — {x.exam_date}</span>
            <button className="danger small" onClick={() => removeExam(x.id)}>Delete</button>
          </li>
        ))}
        {exams.length === 0 && <li className="muted">No upcoming exams.</li>}
      </ul>

      <h3>Mastery map <button className="secondary small" onClick={load}>Refresh</button></h3>
      {mastery.length === 0 && <p className="muted">Answer quizzes or review flashcards to build your mastery map.</p>}
      {mastery.map((m) => (
        <div key={m.concept} className="mastery">
          <span className="concept">{m.concept}</span>
          <div className="bar"><div style={{ width: `${Math.round(m.score * 100)}%` }} /></div>
          <span className="small">{Math.round(m.score * 100)}% · {m.attempts} tries</span>
        </div>
      ))}

      <h3>Study plan</h3>
      <div className="row">
        <label>
          Minutes/day <input type="number" min={15} max={600} value={dailyMinutes} onChange={(e) => setDailyMinutes(+e.target.value)} className="num" />
        </label>
        <label>
          Days <input type="number" min={1} max={14} placeholder="auto" value={days} onChange={(e) => setDays(e.target.value)} className="num" />
        </label>
        <button onClick={makePlan} disabled={busy}>{busy ? "Planning…" : "Make plan"}</button>
      </div>
      {plan && <PlanView plan={plan} />}
    </div>
  );
}
