import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, api, authHeader, call, errorMessage, type Document } from "../api/client";
import { ErrorBox } from "./ErrorBox";

export function Documents({ courseId }: { courseId: string }) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setDocs(await call(api.GET("/api/courses/{course_id}/documents", { params: { path: { course_id: courseId } } })));
    } catch (e) {
      setError(e);
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll every 2 s while anything is still processing.
  const processing = docs.some((d) => d.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [processing, load]);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const files = fileRef.current?.files;
    if (!files?.length) return;
    const form = new FormData();
    for (const f of files) form.append("files", f);
    setUploading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/courses/${courseId}/documents`, {
        method: "POST",
        headers: await authHeader(), // browser sets the multipart boundary
        body: form,
      });
      if (!res.ok) throw new Error(`${res.status}: ${errorMessage(await res.json().catch(() => ({})))}`);
      if (fileRef.current) fileRef.current.value = "";
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setUploading(false);
    }
  }

  async function remove(d: Document) {
    try {
      await call(
        api.DELETE("/api/courses/{course_id}/documents/{document_id}", {
          params: { path: { course_id: courseId, document_id: d.id } },
        }),
      );
      setDocs((ds) => ds.filter((x) => x.id !== d.id));
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div>
      <h3>Course material</h3>
      <p className="muted">PDF, PPTX, DOCX, TXT or MD. Files are parsed and then discarded.</p>
      <ErrorBox error={error} />
      <form onSubmit={upload} className="row">
        <input ref={fileRef} type="file" multiple accept=".pdf,.pptx,.docx,.txt,.md" />
        <button type="submit" disabled={uploading}>{uploading ? "Uploading…" : "Upload"}</button>
        <button type="button" className="secondary" onClick={load}>Refresh</button>
      </form>
      <table>
        <thead>
          <tr><th>File</th><th>Status</th><th>Chunks</th><th /></tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td>{d.filename}</td>
              <td>
                <span className={`badge ${d.status}`}>{d.status}</span>
                {d.error && <div className="error small">{d.error}</div>}
              </td>
              <td>{d.chunk_count}</td>
              <td><button className="danger small" onClick={() => remove(d)}>Delete</button></td>
            </tr>
          ))}
          {docs.length === 0 && (
            <tr><td colSpan={4} className="muted">No documents yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
