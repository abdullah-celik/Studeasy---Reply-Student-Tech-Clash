import { useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { API_URL, api, call, supabase, type Course, type Features, type Preferences } from "./api/client";
import { Auth } from "./components/Auth";
import { Dashboard } from "./components/Dashboard";
import { Loader } from "./components/Loader";
import { Logo } from "./components/Logo";
import { PixelIcon } from "./components/PixelIcon";
import { Settings } from "./components/Settings";
import { Workspace } from "./components/Workspace";
import { useRoute, type Route } from "./lib/router";
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
  const [features, setFeatures] = useState<Features | null>(null);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const theme = useTheme();
  const { route, navigate } = useRoute();
  // Where "Back" in Settings returns to.
  const beforeSettings = useRef<Route>({ name: "home" });

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

  // The URL names a course (e.g. after a refresh): load it, or go home if it's gone.
  const routeCourseId = route.name === "course" ? route.courseId : null;
  const [courseError, setCourseError] = useState(false);
  useEffect(() => {
    if (!userId || !routeCourseId || course?.id === routeCourseId) return;
    let cancelled = false;
    setCourseError(false);
    call(api.GET("/api/courses/{course_id}", { params: { path: { course_id: routeCourseId } } }))
      .then((c) => !cancelled && setCourse(c))
      .catch(() => {
        if (cancelled) return;
        setCourseError(true);
        navigate({ name: "home" }, "replace");
      });
    return () => {
      cancelled = true;
    };
  }, [userId, routeCourseId, course?.id, navigate]);

  function home() {
    navigate({ name: "home" });
  }

  function openCourse(c: Course) {
    setCourse(c);
    navigate({ name: "course", courseId: c.id, mode: null, item: null });
  }

  function toggleSettings() {
    if (route.name === "settings") navigate(beforeSettings.current);
    else {
      beforeSettings.current = route;
      navigate({ name: "settings" });
    }
  }

  if (loading) return <div className="app-loading"><Loader quick size="lg" /></div>;

  const showSettings = route.name === "settings";
  const activeCourse = route.name === "course" && course?.id === route.courseId ? course : null;
  const inCourse = !!session && route.name === "course";

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
                onClick={toggleSettings}
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
          <button className="secondary small back" onClick={toggleSettings}>
            <PixelIcon name="back" size={12} /> Back
          </button>
          <Settings features={features} prefs={prefs} onPrefs={setPrefs} email={session.user.email} theme={theme} />
        </div>
      ) : route.name === "course" ? (
        activeCourse ? (
          <Workspace
            key={activeCourse.id}
            course={activeCourse}
            features={features}
            prefs={prefs}
            onPrefs={setPrefs}
            onBack={home}
            mode={route.mode}
            item={route.item}
            onRoute={(mode, item, how) => navigate({ name: "course", courseId: activeCourse.id, mode, item }, how)}
          />
        ) : courseError ? null : (
          <Loader quick label="Opening course…" />
        )
      ) : (
        <Dashboard onOpen={openCourse} />
      )}
    </div>
  );
}
