import { useEffect, useRef, useState } from "react";
import type { Course, Features, Preferences } from "../api/client";
import { store } from "../lib/format";
import { ChatMode } from "../modes/ChatMode";
import { FlashcardsMode } from "../modes/FlashcardsMode";
import { PlanMode } from "../modes/PlanMode";
import { QuizMode } from "../modes/QuizMode";
import { ReelsMode } from "../modes/ReelsMode";
import type { Mode, ModeProps } from "../modes/types";
import { PixelIcon, type IconName } from "./PixelIcon";
import { useDocuments } from "../lib/useDocuments";
import { Sources } from "./Sources";

const MODES: { id: Mode; label: string; icon: IconName }[] = [
  { id: "chat", label: "Chat", icon: "chat" },
  { id: "quiz", label: "Quiz", icon: "quiz" },
  { id: "flashcards", label: "Flashcards", icon: "cards" },
  { id: "reels", label: "Reels", icon: "reels" },
  { id: "plan", label: "Plan", icon: "plan" },
];

type Drawer = "history" | "sources" | null;

export function Workspace({
  course,
  features,
  prefs,
  onPrefs,
  onBack,
}: {
  course: Course;
  features: Features | null;
  prefs: Preferences | null;
  onPrefs: (p: Preferences) => void;
  onBack: () => void;
}) {
  const modes = MODES.filter((m) => m.id !== "reels" || features?.reels);
  const storeKey = `studeasy:mode:${course.id}`;
  const [mode, setMode] = useState<Mode>(() => {
    const saved = store.get(storeKey) as Mode | null;
    return saved && MODES.some((m) => m.id === saved) ? saved : "chat";
  });
  const current = modes.some((m) => m.id === mode) ? mode : "chat";
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const docs = useDocuments(course.id);
  const hasMaterial = docs.docs.some((d) => d.status === "ready");
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => store.set(storeKey, current), [storeKey, current]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  function cite(filename: string) {
    setHighlight(filename);
    // Sources is a drawer only on narrower screens (see index.css breakpoints).
    if (window.matchMedia("(max-width: 1180px)").matches) setDrawer("sources");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setHighlight(null), 2500);
  }

  const props: ModeProps = { courseId: course.id, hasMaterial, onCite: cite, features, prefs, onPrefs };

  return (
    <div
      className={`workspace ${drawer ? `drawer-${drawer}` : ""}`}
      onClick={(e) => {
        // Picking something in a drawer closes it on small screens.
        if (drawer && (e.target as HTMLElement).closest(".hist-main, .hist-new, .hist-pinned")) setDrawer(null);
      }}
    >
      <div className="ws-bar">
        <button className="secondary small" onClick={onBack} aria-label="All courses">
          <PixelIcon name="back" size={12} /> <span className="hide-sm">Courses</span>
        </button>
        <h1 className="ws-title" title={course.name}>{course.name}</h1>
        <nav className="modes" aria-label="Study modes">
          {modes.map((m) => (
            <button
              key={m.id}
              className={`mode mode-${m.id} ${m.id === current ? "active" : ""}`}
              aria-current={m.id === current ? "page" : undefined}
              onClick={() => {
                setMode(m.id);
                setDrawer(null);
              }}
            >
              <PixelIcon name={m.icon} size={14} /> <span>{m.label}</span>
            </button>
          ))}
        </nav>
        <div className="drawer-toggles">
          <button className={`secondary icon ${drawer === "history" ? "active" : ""}`} aria-label="History" title="History" onClick={() => setDrawer((d) => (d === "history" ? null : "history"))}>
            <PixelIcon name="panel" />
          </button>
          <button className={`secondary icon ${drawer === "sources" ? "active" : ""}`} aria-label="Sources" title="Sources" onClick={() => setDrawer((d) => (d === "sources" ? null : "sources"))}>
            <PixelIcon name="folder" />
          </button>
        </div>
      </div>

      <div className="ws-grid">
        {current === "chat" && <ChatMode key={course.id} {...props} />}
        {current === "quiz" && <QuizMode key={course.id} {...props} />}
        {current === "flashcards" && <FlashcardsMode key={course.id} {...props} />}
        {current === "reels" && <ReelsMode key={course.id} {...props} />}
        {current === "plan" && <PlanMode key={course.id} {...props} />}
        <Sources courseId={course.id} state={docs} highlight={highlight} />
        {drawer && <div className="scrim" onClick={() => setDrawer(null)} />}
      </div>
    </div>
  );
}
