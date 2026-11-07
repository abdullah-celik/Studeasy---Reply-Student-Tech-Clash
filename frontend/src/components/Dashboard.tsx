import { useEffect, useState } from "react";
import { api, call, type Course } from "../api/client";
import { timeAgo } from "../lib/format";
import { ErrorBox } from "./ErrorBox";
import { PixelIcon } from "./PixelIcon";

const TINTS = ["lavender", "mint", "peach", "sky", "pink", "butter"];

function tint(id: string) {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

export function Dashboard({ onOpen }: { onOpen: (c: Course) => void }) {
  const [courses, setCourses] = useState<Course[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    call(api.GET("/api/courses")).then(setCourses).catch((e) => {
      setError(e);
      setCourses([]);
    });
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      const c = await call(api.POST("/api/courses", { body: { name: name.trim(), description: description.trim() || null } }));
      setName("");
      setDescription("");
      setCreating(false);
      onOpen(c); // straight into the new course: next step is adding material
    } catch (e) {
      setError(e);
    }
  }

  async function remove(c: Course) {
    if (!confirm(`Delete “${c.name}” with all its material, chats and quizzes?`)) return;
    try {
      await call(api.DELETE("/api/courses/{course_id}", { params: { path: { course_id: c.id } } }));
      setCourses((cs) => cs?.filter((x) => x.id !== c.id) ?? null);
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className="dashboard">
      <h1>Your courses</h1>
      <ErrorBox error={error} />
      <div className="course-grid">
        {courses?.map((c) => (
          <div key={c.id} className={`course-panel tint-${tint(c.id)}`}>
            <button className="course-open" onClick={() => onOpen(c)}>
              <PixelIcon name="book" size={28} />
              <span className="course-name">{c.name}</span>
              {c.description && <span className="course-desc">{c.description}</span>}
              <span className="muted small">created {timeAgo(c.created_at)}</span>
            </button>
            <button className="mini course-delete" aria-label={`Delete ${c.name}`} title="Delete course" onClick={() => remove(c)}>
              <PixelIcon name="trash" size={10} />
            </button>
          </div>
        ))}

        {creating ? (
          <form className="course-panel new" onSubmit={create}>
            <input autoFocus placeholder="Course name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
            <input placeholder="Short description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
            <div className="row">
              <button type="submit" disabled={!name.trim()}>Create</button>
              <button type="button" className="secondary" onClick={() => setCreating(false)}>Cancel</button>
            </div>
          </form>
        ) : (
          <button className="course-panel add" onClick={() => setCreating(true)}>
            <PixelIcon name="plus" size={28} />
            <span>New course</span>
          </button>
        )}
      </div>
      {courses === null && <p className="muted">Loading…</p>}
      {courses?.length === 0 && !creating && <p className="muted center">Create your first course, then drop in your notes or slides.</p>}
    </div>
  );
}
