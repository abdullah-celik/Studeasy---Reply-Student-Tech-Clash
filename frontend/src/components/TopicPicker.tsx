import { useEffect, useState } from "react";
import { api, call } from "../api/client";

/** Topic input with one-click chips for the course's known concepts (weakest first). */
export function TopicPicker({ courseId, value, onChange }: { courseId: string; value: string; onChange: (v: string) => void }) {
  const [concepts, setConcepts] = useState<string[]>([]);
  useEffect(() => {
    call(api.GET("/api/courses/{course_id}/mastery", { params: { path: { course_id: courseId } } }))
      .then((m) => setConcepts(m.slice(0, 8).map((x) => x.concept)))
      .catch(() => {});
  }, [courseId]);

  return (
    <div className="field">
      <label className="field-label" htmlFor="topic">Topic <span className="muted small">(optional — leave empty for the whole course)</span></label>
      <input id="topic" placeholder="e.g. photosynthesis" value={value} onChange={(e) => onChange(e.target.value)} />
      {concepts.length > 0 && (
        <div className="chips">
          <span className="muted small">Weakest first:</span>
          {concepts.map((c) => (
            <button type="button" key={c} className={`chip ${value === c ? "on" : ""}`} onClick={() => onChange(value === c ? "" : c)}>
              {c}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
