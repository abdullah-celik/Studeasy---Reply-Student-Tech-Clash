import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { API_URL, api, call, supabase, type Course, type Features, type Preferences } from "./api/client";
import { Auth } from "./components/Auth";
import { Chat } from "./components/Chat";
import { Courses } from "./components/Courses";
import { Documents } from "./components/Documents";
import { Flashcards } from "./components/Flashcards";
import { PixelIcon, type IconName } from "./components/PixelIcon";
import { Planning } from "./components/Planning";
import { Quizzes } from "./components/Quizzes";
import { Reels } from "./components/Reels";
import { Settings } from "./components/Settings";

type Tab = "Material" | "Chat" | "Quiz" | "Flashcards" | "Reels" | "Planning";
const TAB_ICON: Record<Tab, IconName> = {
  Material: "folder",
  Chat: "chat",
  Quiz: "quiz",
  Flashcards: "cards",
  Reels: "reels",
  Planning: "plan",
};

function HealthBadge() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((r) => setOk(r.ok))
      .catch(() => setOk(false));
  }, []);
  return (
    <span className={`badge ${ok === null ? "processing" : ok ? "ready" : "failed"}`} title={API_URL}>
      <span className="dot" /> API {ok === null ? "…" : ok ? "online" : "offline"}
    </span>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [course, setCourse] = useState<Course | null>(null);
  const [tab, setTab] = useState<Tab>("Material");
  const [showSettings, setShowSettings] = useState(false);
  const [features, setFeatures] = useState<Features | null>(null);
  const [prefs, setPrefs] = useState<Preferences | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    // Server-side optional modules (no auth needed).
    call(api.GET("/api/features")).then(setFeatures).catch(() => setFeatures({ reels: false }));
    return () => data.subscription.unsubscribe();
  }, []);

  const userId = session?.user.id;
  useEffect(() => {
    if (!userId) {
      setPrefs(null);
      return;
    }
    call(api.GET("/api/me/preferences")).then(setPrefs).catch(() => setPrefs(null));
  }, [userId]);

  const showReels = !!features?.reels && !!prefs?.reels_enabled;
  const tabs: Tab[] = ["Material", "Chat", "Quiz", "Flashcards", ...(showReels ? (["Reels"] as const) : []), "Planning"];
  const currentTab = tabs.includes(tab) ? tab : "Material";

  function home() {
    setCourse(null);
    setShowSettings(false);
  }

  if (loading) return <p className="container muted">Loading…</p>;

  return (
    <div className="container">
      <header>
        <button className="logo" onClick={home}>
          <PixelIcon name="book" size={24} /> <span>Studeasy</span>
        </button>
        <HealthBadge />
        {session && (
          <span className="header-actions">
            <span className="muted small email">{session.user.email}</span>
            <button
              className={`secondary icon ${showSettings ? "active" : ""}`}
              aria-label="Settings"
              title="Settings"
              onClick={() => setShowSettings((s) => !s)}
            >
              <PixelIcon name="gear" />
            </button>
            <button className="secondary small" onClick={() => supabase.auth.signOut()}>Sign out</button>
          </span>
        )}
      </header>

      {!session ? (
        <Auth />
      ) : showSettings ? (
        <>
          <button className="secondary small back" onClick={() => setShowSettings(false)}>
            <PixelIcon name="back" size={12} /> Back
          </button>
          <Settings features={features} prefs={prefs} onPrefs={setPrefs} email={session.user.email} />
        </>
      ) : !course ? (
        <Courses
          onOpen={(c) => {
            setCourse(c);
            setTab("Material");
          }}
        />
      ) : (
        <div className="card">
          <button className="secondary small back" onClick={() => setCourse(null)}>
            <PixelIcon name="back" size={12} /> All courses
          </button>
          <h2>{course.name}</h2>
          {course.description && <p className="muted">{course.description}</p>}
          <nav className="tabs">
            {tabs.map((t) => (
              <button key={t} className={`tab-${t} ${t === currentTab ? "active" : ""}`} onClick={() => setTab(t)}>
                <PixelIcon name={TAB_ICON[t]} size={14} /> {t}
              </button>
            ))}
          </nav>
          {currentTab === "Material" && <Documents courseId={course.id} />}
          {currentTab === "Chat" && <Chat courseId={course.id} />}
          {currentTab === "Quiz" && <Quizzes courseId={course.id} />}
          {currentTab === "Flashcards" && <Flashcards courseId={course.id} />}
          {currentTab === "Reels" && <Reels courseId={course.id} onOpenSettings={() => setShowSettings(true)} />}
          {currentTab === "Planning" && <Planning courseId={course.id} />}
          {features?.reels && !prefs?.reels_enabled && (
            <p className="muted small hint">
              Tip: turn on <button className="link" onClick={() => setShowSettings(true)}>study reels</button> for a swipeable review feed.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
