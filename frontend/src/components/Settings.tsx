import { useState } from "react";
import { api, call, type Features, type Preferences } from "../api/client";
import { ErrorBox } from "./ErrorBox";

export function Settings({
  features,
  prefs,
  onPrefs,
  email,
}: {
  features: Features | null;
  prefs: Preferences | null;
  onPrefs: (p: Preferences) => void;
  email?: string;
}) {
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function toggleReels(on: boolean) {
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

  return (
    <div className="card">
      <h2>Settings</h2>
      {email && <p className="muted">Signed in as {email}</p>}
      <ErrorBox error={error} />

      <div className="setting">
        <div>
          <strong>Study reels</strong>
          <p className="muted small">
            A swipeable feed of short cards (explainers, quick quizzes, flashcards, myth vs fact,
            mnemonics) built from your weakest concepts.
          </p>
          {features && !features.reels && (
            <p className="notice small">Reels are turned off on this server.</p>
          )}
        </div>
        <label className={`switch ${!features?.reels ? "disabled" : ""}`}>
          <input
            type="checkbox"
            checked={!!prefs?.reels_enabled}
            disabled={busy || !features?.reels || !prefs}
            onChange={(e) => toggleReels(e.target.checked)}
          />
          <span className="track" />
        </label>
      </div>
    </div>
  );
}
