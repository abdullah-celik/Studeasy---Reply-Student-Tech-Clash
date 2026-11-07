import { useState, type ReactNode } from "react";
import { Loader } from "./Loader";
import { PixelIcon, type IconName } from "./PixelIcon";

export type HistoryItem = {
  id: string;
  title: string;
  subtitle?: string;
  badge?: ReactNode;
};

/** Left sidebar shared by every mode: "new" button + that mode's earlier items. */
export function HistoryList({
  title,
  icon,
  newLabel,
  onNew,
  newActive,
  items,
  selectedId,
  onSelect,
  onDelete,
  onRename,
  loading,
  empty,
  pinned,
}: {
  title: string;
  icon: IconName;
  newLabel: string;
  onNew: () => void;
  newActive?: boolean;
  items: HistoryItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete?: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  loading?: boolean;
  empty: string;
  pinned?: ReactNode;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  return (
    <aside className="ws-history" aria-label={`${title} history`}>
      <button className={`hist-new ${newActive ? "active" : ""}`} onClick={onNew}>
        <span className="plus">+</span> {newLabel}
      </button>
      {pinned}
      <div className="hist-head">
        <PixelIcon name={icon} size={12} /> {title}
      </div>
      <ul className="hist-list">
        {loading && items.length === 0 && <li className="hist-empty"><Loader inline size="sm" label="Loading…" /></li>}
        {!loading && items.length === 0 && <li className="muted small hist-empty">{empty}</li>}
        {items.map((it) => (
          <li key={it.id} className={`hist-item ${it.id === selectedId ? "selected" : ""}`}>
            {editing === it.id ? (
              <form
                className="hist-rename"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (draft.trim()) onRename?.(it.id, draft.trim());
                  setEditing(null);
                }}
              >
                <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={() => setEditing(null)} maxLength={200} />
              </form>
            ) : (
              <button className="hist-main" onClick={() => onSelect(it.id)} title={it.title}>
                <span className="hist-title">{it.title}</span>
                <span className="hist-sub">
                  {it.subtitle}
                  {it.badge}
                </span>
              </button>
            )}
            {editing !== it.id && (onRename || onDelete) && (
              <span className="hist-actions">
                {onRename && (
                  <button
                    className="mini"
                    aria-label="Rename"
                    title="Rename"
                    onClick={() => {
                      setDraft(it.title);
                      setEditing(it.id);
                    }}
                  >
                    <PixelIcon name="pencil" size={10} />
                  </button>
                )}
                {onDelete && (
                  <button
                    className="mini"
                    aria-label="Delete"
                    title="Delete"
                    onClick={() => {
                      if (confirm(`Delete “${it.title}”?`)) onDelete(it.id);
                    }}
                  >
                    <PixelIcon name="trash" size={10} />
                  </button>
                )}
              </span>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
