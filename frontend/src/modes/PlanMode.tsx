import { useCallback, useEffect, useState } from "react";
import { api, call, type Exam, type MasteryItem, type SavedPlan } from "../api/client";
import { ErrorBox } from "../components/ErrorBox";
import { HistoryList } from "../components/HistoryList";
import { Loader } from "../components/Loader";
import { PlanView } from "../components/PlanView";
import { pct, timeAgo } from "../lib/format";
import type { ModeProps } from "./types";

function daysUntil(iso: string): number {
  const d = new Date(iso + "T00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((d.getTime() - today.getTime()) / 86400000);
}

function NewPlan({ courseId, hasMaterial, onCreated }: { courseId: string; hasMaterial: boolean; onCreated: (p: SavedPlan) => void }) {
  const path = { course_id: courseId };
  const [exams, setExams] = useState<Exam[]>([]);
  const [mastery, setMastery] = useState<MasteryItem[]>([]);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [minutes, setMinutes] = useState(60);
  const [days, setDays] = useState(0); // 0 = until next exam
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    const p = { params: { path: { course_id: courseId } } };
    try {
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

  async function make() {
    setBusy(true);
    setError(null);
    try {
      onCreated(await call(api.POST("/api/courses/{course_id}/plans", { params: { path }, body: { daily_minutes: minutes, days: days || null } })));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (busy) return <Loader size="lg" label="Planning your study days…" />;

  return (
    <div className="new-form wide">
      <h2>New study plan</h2>
      <p className="muted">The planner schedules your weakest concepts first and works back from your next exam.</p>
      <ErrorBox error={error} />

      <div className="plan-grid">
        <div className="panel">
          <h3>Exams</h3>
          <ul className="list">
            {exams.map((x) => {
              const d = daysUntil(x.exam_date);
              return (
                <li key={x.id}>
                  <span>
                    <strong>{x.title}</strong>
                    <span className="muted small"> · {x.exam_date} · {d === 0 ? "today" : `in ${d} day${d === 1 ? "" : "s"}`}</span>
                  </span>
                  <button className="mini" aria-label={`Delete ${x.title}`} onClick={() => removeExam(x.id)}>×</button>
                </li>
              );
            })}
            {exams.length === 0 && <li className="muted small">No upcoming exams. Add one so the plan knows your deadline.</li>}
          </ul>
          <form onSubmit={addExam} className="row wrap">
            <input placeholder="Exam title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
            <button type="submit" className="secondary">Add</button>
          </form>
        </div>

        <div className="panel">
          <h3>Mastery</h3>
          {mastery.length === 0 && <p className="muted small">Answer quizzes or review flashcards to build your mastery map.</p>}
          {mastery.slice(0, 10).map((m) => (
            <div key={m.concept} className="mastery">
              <span className="concept" title={m.concept}>{m.concept}</span>
              <div className="bar"><div style={{ width: pct(m.score) }} /></div>
              <span className="small muted">{pct(m.score)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="field">
        <label className="field-label" htmlFor="mins">Minutes per day: {minutes}</label>
        <input id="mins" type="range" min={15} max={240} step={15} value={minutes} onChange={(e) => setMinutes(+e.target.value)} />
      </div>
      <div className="field">
        <label className="field-label" htmlFor="days">Length: {days === 0 ? (exams[0] ? `until ${exams[0].title}` : "7 days (default)") : `${days} day${days === 1 ? "" : "s"}`}</label>
        <input id="days" type="range" min={0} max={14} value={days} onChange={(e) => setDays(+e.target.value)} />
      </div>
      <button onClick={make} disabled={busy || !hasMaterial}>{busy ? "Planning…" : "Make plan"}</button>
      {!hasMaterial && <p className="muted small">Add course material in Sources first.</p>}
    </div>
  );
}

export function PlanMode({ courseId, hasMaterial, item, onItem }: ModeProps) {
  const [plans, setPlans] = useState<SavedPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<string | null>(item);
  // Keep the open item in the URL (?item=) so a refresh reopens it.
  useEffect(() => {
    if (active !== item) onItem(active);
  }, [active, item, onItem]);

  useEffect(() => {
    call(api.GET("/api/courses/{course_id}/plans", { params: { path: { course_id: courseId } } }))
      .then((ps) => {
        setPlans(ps);
        setActive((a) => (a && !ps.some((p) => p.id === a) ? null : a));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [courseId]);

  async function remove(id: string) {
    await call(api.DELETE("/api/courses/{course_id}/plans/{plan_id}", { params: { path: { course_id: courseId, plan_id: id } } }));
    setPlans((ps) => ps.filter((p) => p.id !== id));
    if (active === id) setActive(null);
  }

  const plan = plans.find((p) => p.id === active);

  return (
    <>
      <HistoryList
        title="Plans"
        icon="plan"
        newLabel="New plan"
        newActive={active === null}
        onNew={() => setActive(null)}
        items={plans.map((p) => ({
          id: p.id,
          title: p.days.length ? `${p.days.length}-day plan from ${new Date(p.days[0].date + "T00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" })}` : "Study plan",
          subtitle: `${timeAgo(p.created_at)} · ${p.daily_minutes} min/day`,
        }))}
        selectedId={active}
        onSelect={setActive}
        onDelete={(id) => remove(id).catch(() => {})}
        loading={loading}
        empty="Plans you make (here or in chat) appear here."
      />
      <section className="ws-main">
        {plan ? (
          <div>
            <div className="main-head">
              <div>
                <h2>Study plan</h2>
                <p className="muted small">{plan.days.length} days · {plan.daily_minutes} min/day · made {timeAgo(plan.created_at)}</p>
              </div>
              <button className="danger small" onClick={() => confirm("Delete this plan?") && remove(plan.id).catch(() => {})}>Delete</button>
            </div>
            <PlanView plan={plan} />
          </div>
        ) : (
          <NewPlan
            courseId={courseId}
            hasMaterial={hasMaterial}
            onCreated={(p) => {
              setPlans((ps) => [p, ...ps]);
              setActive(p.id);
            }}
          />
        )}
      </section>
    </>
  );
}
