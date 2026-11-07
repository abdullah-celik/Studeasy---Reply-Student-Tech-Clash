import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { API_URL, api, call, supabase, type Course, type Features, type Preferences } from "./api/client";
import { Auth } from "./components/Auth";
import { Dashboard } from "./components/Dashboard";
import { Loader } from "./components/Loader";
import { Logo } from "./components/Logo";
import { PixelIcon } from "./components/PixelIcon";
import { Settings } from "./components/Settings";
import { Workspace } from "./components/Workspace";
import { useTheme } from "./lib/theme";


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
  const [showSettings, setShowSettings] = useState(false);
  const [features, setFeatures] = useState<Features | null>(null);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const theme = useTheme();

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
      setCourse(null);
      return;
    }
    call(api.GET("/api/me/preferences")).then(setPrefs).catch(() => setPrefs(null));
  }, [userId]);

  function home() {
    setCourse(null);
    setShowSettings(false);
  }

  if (loading) return <div className="app-loading"><Loader quick size="lg" /></div>;

  const inCourse = !!session && !!course && !showSettings;

  return (
    <div className={inCourse ? "app app-wide" : "app container"}>
      <header>
        <button className="logo" onClick={home}>
          <Logo size={32} /> <span>Studeasy</span>
        </button>
        <HealthBadge />
        <span className="header-actions">
          {session && <span className="muted small email">{session.user.email}</span>}
          <button
            className="secondary icon theme-toggle"
            aria-label={theme.effective === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme.effective === "dark" ? "Light theme" : "Dark theme"}
            onClick={theme.toggle}
          >
            <PixelIcon name={theme.effective === "dark" ? "sun" : "moon"} />
          </button>
          {session && (
            <>
              <button
                className={`secondary icon ${showSettings ? "active" : ""}`}
                aria-label="Settings"
                title="Settings"
                onClick={() => setShowSettings((s) => !s)}
              >
                <PixelIcon name="gear" />
              </button>
              <button className="secondary small" onClick={() => supabase.auth.signOut()}>Sign out</button>
            </>
          )}
        </span>
      </header>

      {!session ? (
        <Auth />
      ) : showSettings ? (
        <div className="container-inner">
          <button className="secondary small back" onClick={() => setShowSettings(false)}>
            <PixelIcon name="back" size={12} /> Back
          </button>
          <Settings features={features} prefs={prefs} onPrefs={setPrefs} email={session.user.email} theme={theme} />
        </div>
      ) : course ? (
        <Workspace key={course.id} course={course} features={features} prefs={prefs} onPrefs={setPrefs} onBack={() => setCourse(null)} />
      ) : (
        <Dashboard onOpen={setCourse} />
      )}
    </div>
  );
}
