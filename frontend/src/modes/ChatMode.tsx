import { useCallback, useEffect, useState } from "react";
import { api, call, type ChatThread } from "../api/client";
import { Chat } from "../components/Chat";
import { HistoryList } from "../components/HistoryList";
import { timeAgo } from "../lib/format";
import type { ModeProps } from "./types";

export function ChatMode({ courseId, hasMaterial, onCite, item, onItem }: ModeProps) {
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<string | null>(item);
  // Remount the conversation only when the student switches threads, not when a new
  // chat gets its id on the first message (that would cut the stream).
  const [chatKey, setChatKey] = useState(0);

  // Keep the open item in the URL (?item=) so a refresh reopens it.
  useEffect(() => {
    if (active !== item) onItem(active);
  }, [active, item, onItem]);

  function open(id: string | null) {
    if (id === active) return;
    setActive(id);
    setChatKey((k) => k + 1);
  }

  const load = useCallback(async () => {
    try {
      const ts = await call(api.GET("/api/courses/{course_id}/chats", { params: { path: { course_id: courseId } } }));
      setThreads(ts);
      // A chat id from the URL that no longer exists: start a new chat instead.
      setActive((a) => (a && !ts.some((t) => t.id === a) ? null : a));
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  async function remove(id: string) {
    await call(api.DELETE("/api/chats/{chat_id}", { params: { path: { chat_id: id } } }));
    setThreads((ts) => ts.filter((t) => t.id !== id));
    if (active === id) open(null);
  }

  async function rename(id: string, title: string) {
    const t = await call(api.PATCH("/api/chats/{chat_id}", { params: { path: { chat_id: id } }, body: { title } }));
    setThreads((ts) => ts.map((x) => (x.id === id ? t : x)));
  }

  return (
    <>
      <HistoryList
        title="Chats"
        icon="chat"
        newLabel="New chat"
        newActive={active === null}
        onNew={() => open(null)}
        items={threads.map((t) => ({ id: t.id, title: t.title || "New chat", subtitle: timeAgo(t.updated_at) }))}
        selectedId={active}
        onSelect={open}
        onDelete={(id) => remove(id).catch(() => {})}
        onRename={(id, title) => rename(id, title).catch(() => {})}
        loading={loading}
        empty="Your conversations will appear here."
      />
      <section className="ws-main">
        <Chat
          key={chatKey}
          courseId={courseId}
          chatId={active}
          hasMaterial={hasMaterial}
          onCite={onCite}
          ensureChat={async () => {
            try {
              const t = await call(api.POST("/api/courses/{course_id}/chats", { params: { path: { course_id: courseId } }, body: {} }));
              setThreads((ts) => [t, ...ts]);
              setActive(t.id);
              return t.id;
            } catch {
              // Backend without chat threads (database not migrated yet): use the single course thread.
              return null;
            }
          }}
          onActivity={(what) => {
            // Title is set from the first message; quizzes/plans show up in their own tabs.
            if (what === "message") load().catch(() => {});
          }}
        />
      </section>
    </>
  );
}
