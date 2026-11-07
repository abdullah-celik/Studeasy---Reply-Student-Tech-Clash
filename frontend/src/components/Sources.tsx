import { useRef, useState } from "react";
import { API_URL, api, authHeader, call, errorMessage, type Document } from "../api/client";
import type { DocsState } from "../lib/useDocuments";
import { timeAgo } from "../lib/format";
import { ErrorBox } from "./ErrorBox";
import { Loader } from "./Loader";
import { PixelIcon } from "./PixelIcon";

const ACCEPT = [".pdf", ".pptx", ".docx", ".txt", ".md"];

export function Sources({ courseId, state, highlight }: { courseId: string; state: DocsState; highlight: string | null }) {
  const { docs, setDocs, loaded, error, setError, load } = state;
  const [uploading, setUploading] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function upload(files: File[]) {
    const ok = files.filter((f) => ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext)));
    const skipped = files.length - ok.length;
    if (!ok.length) {
      setError(new Error(`Unsupported file type. Allowed: ${ACCEPT.join(", ")}`));
      return;
    }
    const form = new FormData();
    for (const f of ok) form.append("files", f);
    setUploading(ok.map((f) => f.name));
    setError(skipped ? new Error(`${skipped} file(s) skipped: unsupported type`) : null);
    try {
      const res = await fetch(`${API_URL}/api/courses/${courseId}/documents`, {
        method: "POST",
        headers: await authHeader(), // browser sets the multipart boundary
        body: form,
      });
      if (!res.ok) throw new Error(`${res.status}: ${errorMessage(await res.json().catch(() => ({})))}`);
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setUploading([]);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function remove(d: Document) {
    if (!confirm(`Remove “${d.filename}” from this course?`)) return;
    try {
      await call(api.DELETE("/api/courses/{course_id}/documents/{document_id}", { params: { path: { course_id: courseId, document_id: d.id } } }));
      setDocs((ds) => ds.filter((x) => x.id !== d.id));
    } catch (e) {
      setError(e);
    }
  }

  const ready = docs.filter((d) => d.status === "ready").length;

  return (
    <aside className="ws-sources" aria-label="Course sources">
      <div className="hist-head">
        <PixelIcon name="folder" size={12} /> Sources <span className="count">{ready}/{docs.length}</span>
      </div>

      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          upload([...e.dataTransfer.files]);
        }}
        onClick={() => fileRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && fileRef.current?.click()}
      >
        <PixelIcon name="upload" size={20} />
        {uploading.length ? <Loader anim="rocket" inline size="sm" label={`Uploading ${uploading.length} file(s)…`} /> : <span>Drop files or click to add</span>}
        <span className="muted small">PDF · PPTX · DOCX · TXT · MD</span>
        <input
          ref={fileRef}
          type="file"
          multiple
          hidden
          accept={ACCEPT.join(",")}
          onChange={(e) => e.target.files && upload([...e.target.files])}
        />
      </div>

      <ErrorBox error={error} />

      <ul className="src-list">
        {loaded && docs.length === 0 && (
          <li className="muted small hist-empty">No material yet. Every mode uses these files, so start by adding your notes or slides.</li>
        )}
        {docs.map((d) => (
          <li key={d.id} className={`src-item ${d.status} ${highlight === d.filename ? "highlight" : ""}`}>
            <PixelIcon name="file" size={14} />
            <div className="src-info">
              <span className="src-name" title={d.filename}>{d.filename}</span>
              <span className="hist-sub">
                {d.status === "ready" && `${d.chunk_count} chunks · ${timeAgo(d.created_at)}`}
                {d.status === "processing" && <Loader anim="rocket" inline size="sm" label="reading…" />}
                {d.status === "failed" && <span className="badge failed">failed</span>}
              </span>
              {d.error && <span className="small src-error">{d.error}</span>}
            </div>
            <button className="mini" aria-label={`Remove ${d.filename}`} title="Remove" onClick={() => remove(d)}>
              <PixelIcon name="trash" size={10} />
            </button>
          </li>
        ))}
      </ul>
      <p className="muted small src-note">Originals aren't stored: files are read, indexed, then discarded.</p>
    </aside>
  );
}
