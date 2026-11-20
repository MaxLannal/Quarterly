import { useRef, useState } from "react";
import { PencilIcon, PlusIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import type { Conversation } from "./types";

/**
 * The Ask page's conversations (newest first): open, rename, delete, clear all. A sidebar on
 * wide screens, the content of a drawer on phones.
 */
export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
  onClear,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const startRename = (c: Conversation) => {
    setEditing(c.id);
    setDraft(c.title);
    window.setTimeout(() => input.current?.select(), 0);
  };
  const finish = (save: boolean) => {
    if (save && editing) onRename(editing, draft);
    setEditing(null);
  };

  return (
    <nav aria-label="Conversations" className="flex min-h-0 flex-col gap-3">
      <button
        type="button"
        onClick={onNew}
        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-pill bg-primary px-4 text-button text-on-primary transition-colors hover:bg-primary-hover"
      >
        <PlusIcon size={16} />
        New conversation
      </button>
      {conversations.length === 0 ? (
        <p className="px-1 text-caption text-muted">Your conversations stay in this browser.</p>
      ) : (
        <>
          <p className="px-1 text-caption-uppercase uppercase text-muted">Recent</p>
          <ul className="flex flex-col gap-0.5">
            {conversations.map((c) => (
              <li key={c.id} className="group relative">
                {editing === c.id ? (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      finish(true);
                    }}
                    className="flex items-center gap-1"
                  >
                    <label htmlFor={`rename-${c.id}`} className="sr-only">
                      Conversation name
                    </label>
                    <input
                      ref={input}
                      id={`rename-${c.id}`}
                      value={draft}
                      maxLength={80}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") {
                          e.stopPropagation();
                          finish(false);
                        }
                      }}
                      onBlur={() => finish(true)}
                      className="min-h-11 w-full rounded-lg border border-primary/50 bg-surface-card px-3 text-body-sm text-ink outline-none"
                    />
                  </form>
                ) : (
                  <div className={cn("relative rounded-lg transition-colors", c.id === activeId ? "bg-primary-wash" : "hover:bg-surface-strong")}>
                    <button
                      type="button"
                      onClick={() => onSelect(c.id)}
                      aria-current={c.id === activeId ? "true" : undefined}
                      className={cn(
                        "block min-h-11 w-full truncate rounded-lg py-2 ps-3 pe-[92px] text-start text-body-sm lg:pe-3 lg:group-focus-within:pe-[92px] lg:group-hover:pe-[92px]",
                        c.id === activeId ? "font-medium text-primary" : "text-body-strong",
                      )}
                    >
                      {c.title}
                    </button>
                    <div className="absolute inset-y-0 end-0 flex items-center opacity-100 transition-opacity lg:opacity-0 lg:group-focus-within:opacity-100 lg:group-hover:opacity-100">
                      <button
                        type="button"
                        onClick={() => startRename(c)}
                        aria-label={`Rename “${c.title}”`}
                        className="inline-flex size-11 shrink-0 items-center justify-center rounded-pill text-muted hover:text-ink"
                      >
                        <PencilIcon size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(c.id)}
                        aria-label={`Delete “${c.title}”`}
                        className="inline-flex size-11 shrink-0 items-center justify-center rounded-pill text-muted hover:text-error"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" aria-hidden="true">
                          <path d="M5 7h14M10 7V4.5h4V7M7 7l1 12.5h8L17 7" />
                        </svg>
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <div className="px-1 pt-2">
            {confirmClear ? (
              <div className="flex flex-wrap items-center gap-2 text-caption" role="group" aria-label="Clear all conversations?">
                <span className="text-body">Delete every conversation?</span>
                <button
                  type="button"
                  onClick={() => {
                    setConfirmClear(false);
                    onClear();
                  }}
                  className="min-h-11 rounded-pill px-3 font-medium text-error hover:bg-error-wash"
                >
                  Delete all
                </button>
                <button type="button" onClick={() => setConfirmClear(false)} className="min-h-11 rounded-pill px-3 text-ink hover:bg-surface-strong">
                  Keep
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => setConfirmClear(true)} className="min-h-11 rounded-pill px-2 text-caption text-muted hover:text-error">
                Clear all
              </button>
            )}
          </div>
        </>
      )}
    </nav>
  );
}
