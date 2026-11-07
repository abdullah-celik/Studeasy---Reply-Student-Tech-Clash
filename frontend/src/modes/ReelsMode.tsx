import { useCallback, useEffect, useState } from "react";
import { api, call, type Reel } from "../api/client";
import { ErrorBox } from "../components/ErrorBox";
import { HistoryList } from "../components/HistoryList";
import { Loader } from "../components/Loader";
import { PixelIcon } from "../components/PixelIcon";
import { ReelBody, Reels } from "../components/Reels";
import { TYPE_LABEL, reelId } from "../lib/reels";
import type { ModeProps } from "./types";

type SeenReel = Exclude<Reel, { type: "break" }>;

function reelTitle(r: SeenReel): string {
  switch (r.type) {
    case "explainer":
      return r.content.hook;
    case "quiz":
      return r.content.question;
    case "flashcard":
      return r.content.front;
    case "myth_fact":
      return r.content.myth;
    case "mnemonic":
      return r.content.mnemonic;
  }
}

function EnableReels({ onEnable, busy }: { onEnable: () => void; busy: boolean }) {
  return (
    <div className="empty">
      <PixelIcon name="reels" size={36} />
      <h2>Study reels</h2>
      <p className="muted">
        A swipeable feed of bite-sized cards (explainers, quick quizzes, flashcards, myth vs fact and mnemonics) built from
        your weakest concepts. It suggests a break every so often.
      </p>
      {busy ? <Loader anim="rocket" inline size="sm" label="Turning on…" /> : <button onClick={onEnable}>Turn on reels</button>}
      <p className="muted small">You can turn them off again in settings.</p>
    </div>
  );
}

export function ReelsMode({ courseId, prefs, onPrefs, item, onItem }: ModeProps) {
  const enabled = !!prefs?.reels_enabled;
  const [seen, setSeen] = useState<SeenReel[]>([]);
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<string | null>(item);
  // Keep the previewed reel in the URL (?item=) so a refresh reopens it.
  useEffect(() => {
    if (preview !== item) onItem(preview);
  }, [preview, item, onItem]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    call(api.GET("/api/courses/{course_id}/reels/history", { params: { path: { course_id: courseId }, query: { limit: 100 } } }))
      .then((rs) => {
        const s = rs.filter((r): r is SeenReel => r.type !== "break");
        setSeen(s);
        setPreview((p) => (p && !s.some((r) => r.id === p) ? null : p));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [courseId, enabled]);

  const onSeen = useCallback((r: Reel) => {
    if (r.type === "break") return;
    setSeen((xs) => [r, ...xs.filter((x) => x.id !== r.id)]);
  }, []);

  async function setEnabled(on: boolean) {
    setBusy(true);
    setError(null);
    try {
      onPrefs(await call(api.PATCH("/api/me/preferences", { body: { reels_enabled: on } })));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const shown = seen.find((r) => reelId(r) === preview);

  return (
    <>
      <HistoryList
        title="Seen reels"
        icon="reels"
        newLabel="Back to feed"
        newActive={preview === null}
        onNew={() => setPreview(null)}
        items={seen.map((r) => ({ id: r.id, title: reelTitle(r), subtitle: `${TYPE_LABEL[r.type]} · ${r.concept}` }))}
        selectedId={preview}
        onSelect={setPreview}
        loading={loading}
        empty={enabled ? "Reels you've swiped past appear here." : "Turn on reels to start a feed."}
      />
      <section className="ws-main">
        <ErrorBox error={error} />
        {!enabled ? (
          <EnableReels onEnable={() => setEnabled(true)} busy={busy} />
        ) : shown ? (
          <div className="reels-wrap">
            <div className={`reel type-${shown.type} preview`}>
              <div className="reel-card">
                <div className="reel-head">
                  <span className="tag">{TYPE_LABEL[shown.type]}</span>
                  <span className="muted small">{shown.concept}</span>
                </div>
                <div className="reel-body">
                  <ReelBody key={shown.id} reel={shown} onDone={() => {}} />
                </div>
              </div>
            </div>
            <button className="secondary" onClick={() => setPreview(null)}>Back to feed</button>
          </div>
        ) : (
          // Keep the feed mounted state simple: it re-fetches unseen reels when shown again.
          <Reels courseId={courseId} onSeen={onSeen} onDisabled={() => setEnabled(true)} />
        )}
      </section>
    </>
  );
}
