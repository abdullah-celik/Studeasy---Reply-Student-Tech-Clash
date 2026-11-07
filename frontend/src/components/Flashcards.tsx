import { useCallback, useEffect, useState } from "react";
import { api, call, type Flashcard } from "../api/client";
import { ErrorBox } from "./ErrorBox";

const GRADES = [
  { q: 0, label: "0 Blackout" },
  { q: 1, label: "1" },
  { q: 2, label: "2" },
  { q: 3, label: "3 Hard" },
  { q: 4, label: "4 Good" },
  { q: 5, label: "5 Easy" },
];

export function Flashcards({ courseId }: { courseId: string }) {
  const [due, setDue] = useState<Flashcard[]>([]);
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(10);
  const [flipped, setFlipped] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setDue(await call(api.GET("/api/courses/{course_id}/flashcards/due", { params: { path: { course_id: courseId } } })));
    } catch (e) {
      setError(e);
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await call(
        api.POST("/api/courses/{course_id}/flashcards", {
          params: { path: { course_id: courseId } },
          body: { topic: topic || null, count },
        }),
      );
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function review(card: Flashcard, quality: number) {
    try {
      await call(api.POST("/api/flashcards/{card_id}/review", { params: { path: { card_id: card.id } }, body: { quality } }));
      setFlipped(false);
      setDue((d) => d.filter((c) => c.id !== card.id));
    } catch (e) {
      setError(e);
    }
  }

  const card = due[0];

  return (
    <div>
      <h3>Generate flashcards</h3>
      <form onSubmit={generate} className="row">
        <input placeholder="Topic (optional)" value={topic} onChange={(e) => setTopic(e.target.value)} />
        <label>
          Cards <input type="number" min={1} max={40} value={count} onChange={(e) => setCount(+e.target.value)} className="num" />
        </label>
        <button type="submit" disabled={busy}>{busy ? "Generating…" : "Generate"}</button>
      </form>
      <ErrorBox error={error} />

      <h3>Review ({due.length} due)</h3>
      {!card && <p className="muted">Nothing due right now. Nice work!</p>}
      {card && (
        <div className="flashcard">
          <div className="muted small">{card.concept} · interval {card.interval}d · ease {card.ease.toFixed(2)}</div>
          <p className="front">{card.front}</p>
          {flipped ? (
            <>
              <p className="back">{card.back}</p>
              <div className="row wrap">
                {GRADES.map((g) => (
                  <button key={g.q} className="secondary" onClick={() => review(card, g.q)}>{g.label}</button>
                ))}
              </div>
            </>
          ) : (
            <button onClick={() => setFlipped(true)}>Show answer</button>
          )}
        </div>
      )}
    </div>
  );
}
