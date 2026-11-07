import { useCallback, useEffect, useState } from "react";
import { api, call, type Document } from "../api/client";

/** Course documents, shared by every mode. Polls while something is still processing. */
export function useDocuments(courseId: string) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    try {
      setDocs(await call(api.GET("/api/courses/{course_id}/documents", { params: { path: { course_id: courseId } } })));
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoaded(true);
    }
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  const processing = docs.some((d) => d.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [processing, load]);

  return { docs, setDocs, loaded, error, setError, load };
}

export type DocsState = ReturnType<typeof useDocuments>;

