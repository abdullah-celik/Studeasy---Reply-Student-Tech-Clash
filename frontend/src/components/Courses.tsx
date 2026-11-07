import { useEffect, useState } from "react";
import { api, call, type Course } from "../api/client";
import { ErrorBox } from "./ErrorBox";

export function Courses({ onOpen }: { onOpen: (c: Course) => void }) {
  const [courses, setCourses] = useState<Course[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<unknown>(null);

  async function load() {
    try {
      setCourses(await call(api.GET("/api/courses")));
    } catch (e) {
      setError(e);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      const c = await call(api.POST("/api/courses", { body: { name, description: description || null } }));
      setName("");
      setDescription("");
      setCourses((cs) => [c, ...cs]);
    } catch (e) {
      setError(e);
    }
  }

  async function remove(c: Course) {
    if (!confirm(`Delete "${c.name}" and all its material?`)) return;
    try {
      await call(api.DELETE("/api/courses/{course_id}", { params: { path: { course_id: c.id } } }));
      setCourses((cs) => cs.filter((x) => x.id !== c.id));
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className="card">
      <h2>Your courses</h2>
      <ErrorBox error={error} />
      <form onSubmit={create} className="row">
        <input placeholder="Course name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
        <button type="submit">Create</button>
      </form>
      {courses.length === 0 && <p className="muted">No courses yet.</p>}
      <ul className="list">
        {courses.map((c) => (
          <li key={c.id}>
            <div>
              <strong>{c.name}</strong>
              {c.description && <div className="muted">{c.description}</div>}
            </div>
            <div className="row">
              <button onClick={() => onOpen(c)}>Open</button>
              <button className="danger" onClick={() => remove(c)}>Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
