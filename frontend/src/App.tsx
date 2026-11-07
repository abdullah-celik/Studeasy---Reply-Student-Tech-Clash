import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { API_URL, supabase, type Course } from "./api/client";
import { Auth } from "./components/Auth";
import { Chat } from "./components/Chat";
import { Courses } from "./components/Courses";
import { Documents } from "./components/Documents";
import { Flashcards } from "./components/Flashcards";
import { Planning } from "./components/Planning";
import { Quizzes } from "./components/Quizzes";

const TABS = ["Material", "Chat", "Quiz", "Flashcards", "Planning"] as const;
type Tab = (typeof TABS)[number];

function HealthBadge() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((r) => setOk(r.ok))
      .catch(() => setOk(false));
  }, []);
  return (
    <span className={`badge ${ok === null ? "processing" : ok ? "ready" : "failed"}`} title={API_URL}>
      API {ok === null ? "…" : ok ? "online" : "offline"}
    </span>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [course, setCourse] = useState<Course | null>(null);
  const [tab, setTab] = useState<Tab>("Material");

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  if (loading) return <p className="container muted">Loading…</p>;

  return (
    <div className="container">
      <header>
        <strong className="logo" onClick={() => setCourse(null)}>📚 Studeasy</strong>
        <HealthBadge />
        {session && (
          <span className="row">
            <span className="muted small">{session.user.email}</span>
            <button className="secondary small" onClick={() => supabase.auth.signOut()}>Sign out</button>
          </span>
        )}
      </header>

      {!session ? (
        <Auth />
      ) : !course ? (
        <Courses
          onOpen={(c) => {
            setCourse(c);
            setTab("Material");
          }}
        />
      ) : (
        <div className="card">
          <button className="secondary small" onClick={() => setCourse(null)}>← All courses</button>
          <h2>{course.name}</h2>
          {course.description && <p className="muted">{course.description}</p>}
          <nav className="tabs">
            {TABS.map((t) => (
              <button key={t} className={t === tab ? "active" : ""} onClick={() => setTab(t)}>{t}</button>
            ))}
          </nav>
          {tab === "Material" && <Documents courseId={course.id} />}
          {tab === "Chat" && <Chat courseId={course.id} />}
          {tab === "Quiz" && <Quizzes courseId={course.id} />}
          {tab === "Flashcards" && <Flashcards courseId={course.id} />}
          {tab === "Planning" && <Planning courseId={course.id} />}
        </div>
      )}
    </div>
  );
}
