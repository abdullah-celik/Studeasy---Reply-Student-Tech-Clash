import { useCallback, useEffect, useState } from "react";
import { api, call, type Flashcard, type FlashcardDeck } from "../api/client";
import { ErrorBox } from "../components/ErrorBox";
import { HistoryList } from "../components/HistoryList";
import { Loader } from "../components/Loader";
import { PixelIcon } from "../components/PixelIcon";
import { TopicPicker } from "../components/TopicPicker";
import { timeAgo } from "../lib/format";
import type { ModeProps } from "./types";

const GRADES = [
  { q: 1, label: "Again", hint: "forgot" },
  { q: 3, label: "Hard", hint: "struggled" },
  { q: 4, label: "Good", hint: "recalled" },
  { q: 5, label: "Easy", hint: "instant" },
];

const DUE = "__due__";

function Study({ cards, title, onDone, onReviewed }: { cards: Flashcard[]; title: string; onDone: () => void; onReviewed: () => void }) {
  const [i, setI] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [tally, setTally] = useState<Record<string, number>>({});

  if (cards.length === 0) {
    return (
      <div className="empty">
        <PixelIcon name="star" size={32} />
        <p>Nothing to review right now. Nice work!</p>
        <button className="secondary" onClick={onDone}>Back</button>
      </div>
    );
  }

  if (i >= cards.length) {
    return (
      <div className="empty">
        <PixelIcon name="star" size={32} />
        <h2>Session done</h2>
        <p className="muted">
          {cards.length} cards · {GRADES.map((g) => `${tally[g.label] ?? 0} ${g.label.toLowerCase()}`).join(" · ")}
        </p>
        <button onClick={onDone}>Finish</button>
      </div>
    );
  }

  const card = cards[i];
  async function rate(q: number, label: string) {
    setError(null);
    try {
      await call(api.POST("/api/flashcards/{card_id}/review", { params: { path: { card_id: card.id } }, body: { quality: q } }));
      setTally((t) => ({ ...t, [label]: (t[label] ?? 0) + 1 }));
      setFlipped(false);
      setI((x) => x + 1);
      onReviewed();
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className="study">
      <div className="main-head">
        <div>
          <h2>{title}</h2>
          <p className="muted small">Card {i + 1} of {cards.length} · {card.concept}</p>
        </div>
        <button className="secondary small" onClick={onDone}>Stop</button>
      </div>
      <div className="progress"><div style={{ width: `${(i / cards.length) * 100}%` }} /></div>
      <button className={`flip big ${flipped ? "flipped" : ""}`} onClick={() => setFlipped((f) => !f)}>
        <span className="reel-title">{flipped ? card.back : card.front}</span>
        <span className="muted small">{flipped ? "answer" : "tap to flip"}</span>
      </button>
      {flipped ? (
        <div className="grades">
          {GRADES.map((g) => (
            <button key={g.q} className="secondary" onClick={() => rate(g.q, g.label)}>
              {g.label}
              <span className="muted small">{g.hint}</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="row center"><button onClick={() => setFlipped(true)}>Show answer</button></div>
      )}
      <ErrorBox error={error} />
    </div>
  );
}

function NewDeck({ courseId, hasMaterial, onCreated }: { courseId: string; hasMaterial: boolean; onCreated: (cards: Flashcard[]) => void }) {
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onCreated(await call(api.POST("/api/courses/{course_id}/flashcards", { params: { path: { course_id: courseId } }, body: { topic: topic || null, count } })));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (busy) return <Loader size="lg" label={`Making ${count} card${count === 1 ? "" : "s"}${topic ? ` on ${topic}` : ""}…`} />;

  return (
    <form className="new-form" onSubmit={generate}>
      <h2>New flashcard deck</h2>
      <p className="muted">Cards are scheduled with spaced repetition (SM-2), so each one comes back right before you'd forget it.</p>
      {!hasMaterial && <p className="notice small">Add course material in Sources to generate cards.</p>}
      <TopicPicker courseId={courseId} value={topic} onChange={setTopic} />
      <div className="field">
        <label className="field-label" htmlFor="cards">Cards: {count}</label>
        <input id="cards" type="range" min={1} max={40} value={count} onChange={(e) => setCount(+e.target.value)} />
      </div>
      <ErrorBox error={error} />
      <button type="submit" disabled={busy || !hasMaterial}>{busy ? "Making cards…" : "Generate deck"}</button>
    </form>
  );
}

function DeckView({ deck, onDelete, onReviewed }: { deck: FlashcardDeck; onDelete: () => void; onReviewed: () => void }) {
  const [cards, setCards] = useState<Flashcard[] | null>(null);
  const [studying, setStudying] = useState<Flashcard[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    call(api.GET("/api/flashcards/decks/{deck_id}", { params: { path: { deck_id: deck.id } } }))
      .then(setCards)
      .catch(setError);
  }, [deck.id]);
  useEffect(load, [load]);

  if (error) return <ErrorBox error={error} />;
  if (!cards) return <Loader quick label="Loading deck…" />;

  const now = Date.now();
  const due = cards.filter((c) => new Date(c.due_at).getTime() <= now);
  const title = deck.topic || "Whole course";

  if (studying) {
    return <Study cards={studying} title={title} onReviewed={onReviewed} onDone={() => { setStudying(null); load(); }} />;
  }

  return (
    <div>
      <div className="main-head">
        <div>
          <h2>{title}</h2>
          <p className="muted small">{cards.length} cards · {due.length} due · {timeAgo(deck.created_at)}</p>
        </div>
        <button className="danger small" onClick={() => confirm("Delete this deck and its cards?") && onDelete()}>Delete</button>
      </div>
      <div className="row wrap">
        <button disabled={due.length === 0} onClick={() => setStudying(due)}>Review {due.length} due</button>
        <button className="secondary" disabled={cards.length === 0} onClick={() => setStudying(cards)}>Practice all {cards.length}</button>
      </div>
      <div className="card-grid">
        {cards.map((c) => (
          <details key={c.id} className="mini-card">
            <summary>{c.front}</summary>
            <p>{c.back}</p>
            <span className="muted small">{c.concept} · next {new Date(c.due_at).getTime() <= now ? "now" : timeAgo(c.due_at).replace(" ago", "")}</span>
          </details>
        ))}
      </div>
    </div>
  );
}

export function FlashcardsMode({ courseId, hasMaterial }: ModeProps) {
  const [decks, setDecks] = useState<FlashcardDeck[]>([]);
  const [due, setDue] = useState<Flashcard[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<string | null>(null);
  const [studyKey, setStudyKey] = useState(0);

  const load = useCallback(async () => {
    const p = { params: { path: { course_id: courseId } } };
    try {
      const [d, du] = await Promise.all([
        call(api.GET("/api/courses/{course_id}/flashcards/decks", p)),
        call(api.GET("/api/courses/{course_id}/flashcards/due", p)),
      ]);
      setDecks(d);
      setDue(du);
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  async function remove(id: string) {
    await call(api.DELETE("/api/flashcards/decks/{deck_id}", { params: { path: { deck_id: id } } }));
    if (active === id) setActive(null);
    await load();
  }

  const deck = decks.find((d) => d.id === active);

  return (
    <>
      <HistoryList
        title="Decks"
        icon="cards"
        newLabel="New deck"
        newActive={active === null}
        onNew={() => setActive(null)}
        pinned={
          <button
            className={`hist-pinned ${active === DUE ? "selected" : ""}`}
            onClick={() => {
              setActive(DUE);
              setStudyKey((k) => k + 1);
            }}
          >
            <PixelIcon name="star" size={12} /> Due today <span className="count">{due.length}</span>
          </button>
        }
        items={decks.map((d) => ({
          id: d.id,
          title: d.topic || "Whole course",
          subtitle: `${timeAgo(d.created_at)} · ${d.card_count} cards`,
          badge: d.due_count > 0 ? <span className="score bad">{d.due_count} due</span> : undefined,
        }))}
        selectedId={active}
        onSelect={setActive}
        onDelete={(id) => remove(id).catch(() => {})}
        loading={loading}
        empty="Decks you generate appear here."
      />
      <section className="ws-main">
        {active === DUE ? (
          <Study
            key={studyKey}
            cards={due}
            title="Due today (all decks)"
            onReviewed={() => {}}
            onDone={() => {
              setActive(null);
              load().catch(() => {});
            }}
          />
        ) : deck ? (
          <DeckView key={deck.id} deck={deck} onDelete={() => remove(deck.id).catch(() => {})} onReviewed={() => load().catch(() => {})} />
        ) : (
          <NewDeck
            courseId={courseId}
            hasMaterial={hasMaterial}
            onCreated={async (cards) => {
              await load().catch(() => {});
              setActive(cards[0]?.deck_id ?? null);
            }}
          />
        )}
      </section>
    </>
  );
}
