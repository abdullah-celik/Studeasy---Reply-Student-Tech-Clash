import { useState } from "react";
import type { LegalDoc } from "../lib/legal";
import { LegalDialog, LegalLinks } from "./Legal";
import { api, call, type Features, type Preferences } from "../api/client";
import type { Theme, ThemePref } from "../lib/theme";
import { ErrorBox } from "./ErrorBox";

const THEMES: { id: ThemePref; label: string }[] = [
  { id: "system", label: "System" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
];

export function Settings({
  features,
  prefs,
  onPrefs,
  email,
  theme,
}: {
  features: Features | null;
  prefs: Preferences | null;
  onPrefs: (p: Preferences) => void;
  email?: string;
  theme: Theme;
}) {
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [legal, setLegal] = useState<LegalDoc | null>(null);

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
          <strong>Appearance</strong>
          <p className="muted small">System follows your device's light or dark mode.</p>
        </div>
        <div className="segmented" role="radiogroup" aria-label="Theme">
          {THEMES.map((t) => (
            <button
              key={t.id}
              role="radio"
              aria-checked={theme.pref === t.id}
              className={theme.pref === t.id ? "on" : ""}
              onClick={() => theme.setPref(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

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

      <p className="muted small legal-note">
        <LegalLinks open={setLegal} />
      </p>
      <LegalDialog doc={legal} onClose={() => setLegal(null)} />
    </div>
  );
}
