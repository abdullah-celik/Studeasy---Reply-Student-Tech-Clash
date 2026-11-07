import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, call, type Reel, type ReelAnswerResult } from "../api/client";
import { TYPE_LABEL, reelId } from "../lib/reels";
import { ErrorBox } from "./ErrorBox";
import { Loader } from "./Loader";
import { PixelIcon } from "./PixelIcon";

type Tracked = { reel: Reel; key: string };



/* --- individual cards --------------------------------------------------- */

function QuizCard({ reel, onDone }: { reel: Extract<Reel, { type: "quiz" }>; onDone: () => void }) {
  const [picked, setPicked] = useState<string | null>(null);
  const [result, setResult] = useState<ReelAnswerResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const c = reel.content;
  const options = c.kind === "true_false" && c.options.length === 0 ? ["True", "False"] : c.options;

  async function answer(opt: string) {
    setPicked(opt);
    setError(null);
    try {
      setResult(await call(api.POST("/api/reels/{reel_id}/answer", { params: { path: { reel_id: reel.id } }, body: { response: opt } })));
      onDone();
    } catch (e) {
      setPicked(null);
      setError(e);
    }
  }

  return (
    <>
      <p className="reel-title">{c.question}</p>
      <div className="options">
        {options.map((o) => {
          const state = !result ? "" : o === result.correct_answer ? "right" : o === picked ? "wrong" : "";
          return (
            <button key={o} className={`option ${state} ${picked === o ? "picked" : ""}`} disabled={!!picked} onClick={() => answer(o)}>
              {o}
            </button>
          );
        })}
      </div>
      <ErrorBox error={error} />
      {result && (
        <div className={`result ${result.correct ? "ok" : "bad"}`}>
          <strong>{result.correct ? "Correct!" : `Answer: ${result.correct_answer}`}</strong>
          <div className="small">{result.explanation}</div>
        </div>
      )}
    </>
  );
}

function FlashcardCard({ reel, onDone }: { reel: Extract<Reel, { type: "flashcard" }>; onDone: () => void }) {
  const [flipped, setFlipped] = useState(false);
  const [rated, setRated] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function rate(label: string, quality: number) {
    setError(null);
    try {
      await call(api.POST("/api/flashcards/{card_id}/review", { params: { path: { card_id: reel.content.flashcard_id } }, body: { quality } }));
      setRated(label);
      onDone();
    } catch (e) {
      setError(e);
    }
  }

  return (
    <>
      <button className={`flip ${flipped ? "flipped" : ""}`} onClick={() => setFlipped((f) => !f)}>
        <span className="reel-title">{flipped ? reel.content.back : reel.content.front}</span>
        <span className="muted small">{flipped ? "back" : "tap to flip"}</span>
      </button>
      {flipped && !rated && (
        <div className="row center">
          <button className="secondary" onClick={() => rate("Again", 1)}>Again</button>
          <button className="secondary" onClick={() => rate("Good", 4)}>Good</button>
          <button className="secondary" onClick={() => rate("Easy", 5)}>Easy</button>
        </div>
      )}
      {rated && <p className="muted small center">Rated “{rated}”. See you at the next review.</p>}
      <ErrorBox error={error} />
    </>
  );
}

export function ReelBody({ reel, onDone }: { reel: Reel; onDone: () => void }) {
  switch (reel.type) {
    case "explainer":
      return (
        <>
          <div className="reel-emoji">{reel.content.emoji}</div>
          <p className="reel-title">{reel.content.hook}</p>
          <ul className="pixel-list">{reel.content.points.map((p, i) => <li key={i}>{p}</li>)}</ul>
          <p className="takeaway">{reel.content.takeaway}</p>
        </>
      );
    case "quiz":
      return <QuizCard reel={reel} onDone={onDone} />;
    case "flashcard":
      return <FlashcardCard reel={reel} onDone={onDone} />;
    case "myth_fact":
      return (
        <>
          <div className="myth"><span className="tag bad">Myth</span><p>{reel.content.myth}</p></div>
          <div className="fact"><span className="tag ok">Fact</span><p>{reel.content.fact}</p></div>
          <p className="muted small">{reel.content.why}</p>
        </>
      );
    case "mnemonic":
      return (
        <>
          <p className="reel-title mnemonic">{reel.content.mnemonic}</p>
          <p>{reel.content.explanation}</p>
        </>
      );
    case "break":
      return (
        <>
          <div className="reel-emoji"><PixelIcon name="heart" size={40} /></div>
          <p className="reel-title">{reel.content.title}</p>
          <p>{reel.content.message}</p>
          <p className="muted small">
            {reel.content.reels_watched} reels · {reel.content.minutes} min
            {reel.content.concepts.length > 0 && <> · {reel.content.concepts.join(", ")}</>}
          </p>
        </>
      );
  }
}

/* --- feed ---------------------------------------------------------------- */

export function Reels({
  courseId,
  onDisabled,
  onSeen,
}: {
  courseId: string;
  onDisabled: () => void;
  /** A reel was swiped away (it is now in the history). */
  onSeen: (reel: Reel) => void;
}) {
  const [items, setItems] = useState<Tracked[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [session, setSession] = useState<{ count: number; every: number } | null>(null);

  const scroller = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const seen = useRef(new Set<string>()); // ids already in the list (feed re-returns unseen-but-shown reels)
  const breakSeq = useRef(0);
  const viewStart = useRef<number>(Date.now());
  const done = useRef(new Set<string>()); // reels the student interacted with
  const activeRef = useRef(0);
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const loadMore = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const feed = await call(api.GET("/api/courses/{course_id}/reels/feed", { params: { path: { course_id: courseId } } }));
      setSession({ count: feed.session_reels, every: feed.break_every });
      const fresh: Tracked[] = [];
      for (const r of feed.items) {
        const id = reelId(r);
        if (id) {
          if (seen.current.has(id)) continue;
          seen.current.add(id);
          fresh.push({ reel: r, key: id });
        } else if (fresh.length > 0) {
          // Break card: only keep it if it follows a new reel, so re-fetches don't stack breaks.
          fresh.push({ reel: r, key: `break-${breakSeq.current++}` });
        }
      }
      setItems((xs) => [...xs, ...fresh]);
    } catch (e) {
      setError(e);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    loadMore();
  }, [loadMore]);

  // Report the view when a reel leaves the screen.
  const flushView = useCallback((index: number) => {
    const t = itemsRef.current[index];
    const id = t && reelId(t.reel);
    if (!id) return;
    const watch_ms = Math.min(Date.now() - viewStart.current, 3_600_000);
    const completed = done.current.has(id) || watch_ms >= 4000;
    call(api.POST("/api/reels/{reel_id}/view", { params: { path: { reel_id: id } }, body: { watch_ms, completed } }))
      .then(() => onSeen(t.reel))
      .catch(() => {
        /* view tracking is best-effort */
      });
  }, [onSeen]);

  // Track which card is snapped into view.
  useEffect(() => {
    const root = scroller.current;
    if (!root) return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const i = Number((e.target as HTMLElement).dataset.index);
          if (activeRef.current !== i) {
            flushView(activeRef.current);
            viewStart.current = Date.now();
            activeRef.current = i;
            setActive(i);
          }
        }
      },
      { root, threshold: 0.6 },
    );
    root.querySelectorAll(".reel").forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, [items.length, flushView]);

  // Flush the current reel when leaving the tab.
  useEffect(() => () => flushView(activeRef.current), [flushView]);

  // Prefetch when ~2 reels from the end.
  useEffect(() => {
    if (items.length > 0 && active >= items.length - 2) loadMore();
  }, [active, items.length, loadMore]);

  function go(delta: number) {
    const el = scroller.current?.querySelector<HTMLElement>(`[data-index="${active + delta}"]`);
    el?.scrollIntoView({ behavior: "smooth" });
  }

  const status = error instanceof ApiError ? error.status : null;

  return (
    <div className="reels-wrap">
      {status === 403 ? (
        <div className="empty">
          <p>Reels are turned off for your account.</p>
          <button onClick={onDisabled}>Turn on reels</button>
        </div>
      ) : status === 409 ? (
        <div className="empty"><p>Upload some course material first, then come back for reels.</p></div>
      ) : (
        <ErrorBox error={error} />
      )}

      <div className="reels" ref={scroller} tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); go(1); }
          if (e.key === "ArrowUp") { e.preventDefault(); go(-1); }
        }}
      >
        {items.map(({ reel, key }, i) => {
          const id = reelId(reel);
          return (
            <section key={key} className={`reel type-${reel.type}`} data-index={i}>
              <div className="reel-card">
                <div className="reel-head">
                  <span className="tag">{TYPE_LABEL[reel.type]}</span>
                  {"concept" in reel && <span className="muted small">{reel.concept}</span>}
                </div>
                <div className="reel-body">
                  <ReelBody reel={reel} onDone={() => id && done.current.add(id)} />
                </div>
              </div>
            </section>
          );
        })}
        {(loading || (items.length === 0 && !error)) && (
          <section className="reel">
            <div className="reel-card skeleton">
              <Loader anim="rocket" size="lg" label="Generating reels from your notes…" />
            </div>
          </section>
        )}
      </div>

      <div className="reels-nav">
        <button className="secondary icon" aria-label="Previous reel" disabled={active === 0} onClick={() => go(-1)}><PixelIcon name="up" /></button>
        <span className="small muted">
          {items.length ? `${active + 1} / ${items.length}` : "—"}
          {session && <> · session {session.count}/{session.every}</>}
        </span>
        <button className="secondary icon" aria-label="Next reel" disabled={active >= items.length - 1} onClick={() => go(1)}><PixelIcon name="down" /></button>
      </div>
    </div>
  );
}
