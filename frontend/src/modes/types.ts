import type { Features, Preferences } from "../api/client";

export type Mode = "chat" | "quiz" | "flashcards" | "reels" | "plan";

export type ModeProps = {
  courseId: string;
  /** At least one source is ready. */
  hasMaterial: boolean;
  /** Highlight a source in the right panel (citation chips). */
  onCite: (filename: string) => void;
  features: Features | null;
  prefs: Preferences | null;
  onPrefs: (p: Preferences) => void;
};
