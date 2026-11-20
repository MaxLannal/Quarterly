import { useCallback, useId, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useFocusTrap } from "@/components/ui/dialog";
import { CloseIcon } from "@/components/ui/icons";
import { COMPANION_KEY } from "@/features/ask/conversations";
import { useAskChat } from "@/features/ask/useAskChat";
import "@/features/ask/ask.css";
import { usePresence } from "@/lib/motion";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { CompanionChat } from "./CompanionChat";
import "./companion.css";
import { ForYou } from "./ForYou";
import { contextOf } from "./suggestions";
import { useUnreadCount } from "./updates";

type Tab = "chat" | "foryou";

/**
 * The AI companion on every page but /ask (docs/BEST-OF-UCHICAGO-PLAN.md): a floating maroon
 * orb (with the count of unread updates when logged in) that opens a side panel, a full-screen
 * sheet on phones. "Chat" asks the campus guide with the page's context; "For you" shows what is
 * new on the forum for this student. Escape closes; focus is trapped and goes back to the orb.
 */
export function Companion() {
  const { pathname } = useLocation();
  const session = useSession();
  const account = session.data?.account ?? null;
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("chat");
  const context = useMemo(() => contextOf(pathname), [pathname]);
  const chat = useAskChat({ storageKey: COMPANION_KEY, mode: "companion", context, initialActive: "latest" });
  const unread = useUnreadCount(!!account);
  const hidden = /^\/ask(\/|$)/.test(pathname);
  const close = useCallback(() => setOpen(false), []);

  if (hidden) return null;
  const count = account ? (unread.data ?? 0) : 0;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={count > 0 ? `Open Quarterly companion, ${count} new ${count === 1 ? "update" : "updates"}` : "Open Quarterly companion"}
        aria-haspopup="dialog"
        aria-hidden={open || undefined}
        tabIndex={open ? -1 : undefined}
        className={cn(
          "companion-orb fixed bottom-[max(16px,calc(env(safe-area-inset-bottom)+12px))] right-4 z-40 inline-flex size-12 items-center justify-center rounded-pill bg-primary text-on-primary shadow-overlay transition-transform hover:scale-[1.04] active:scale-[0.97] sm:bottom-6 sm:right-6 sm:size-14",
          open && "invisible",
        )}
      >
        <OrbGlyph />
        {count > 0 && (
          <span aria-hidden="true" className="absolute -right-0.5 -top-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-pill border-2 border-canvas bg-ink px-1 text-[11px] font-semibold tabular-nums text-on-dark">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>
      <Panel open={open} onClose={close} tab={tab} onTab={setTab} unread={count}>
        {tab === "chat" ? (
          <CompanionChat chat={chat} context={context} username={account?.username ?? null} onNavigate={close} open={open} />
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <ForYou loggedIn={!!account} onNavigate={close} />
          </div>
        )}
      </Panel>
    </>
  );
}

function OrbGlyph() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3.5c.7 4.4 2.6 6.3 7 7-4.4.7-6.3 2.6-7 7-.7-4.4-2.6-6.3-7-7 4.4-.7 6.3-2.6 7-7z" fill="currentColor" />
      <circle cx="18.5" cy="17.5" r="1.6" fill="currentColor" opacity=".75" />
    </svg>
  );
}

function Panel({
  open,
  onClose,
  tab,
  onTab,
  unread,
  children,
}: {
  open: boolean;
  onClose: () => void;
  tab: Tab;
  onTab: (t: Tab) => void;
  unread: number;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const presence = usePresence(open, 220);
  useFocusTrap(ref, open, onClose);
  const id = useId();
  if (presence === "closed") return null;
  const closing = presence === "closing";
  const tabs: { key: Tab; label: string }[] = [
    { key: "chat", label: "Chat" },
    { key: "foryou", label: "For you" },
  ];
  const onTabKey = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const next = tab === "chat" ? "foryou" : "chat";
    onTab(next);
    window.setTimeout(() => document.getElementById(`${id}-tab-${next}`)?.focus(), 0);
  };
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- Escape and the Close button are the keyboard path
    <div
      className={cn("fixed inset-0 z-50 flex justify-end", closing ? "bg-ink/0 transition-colors duration-200" : "animate-fade-in bg-ink/25")}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        className={cn(
          "relative flex h-full w-full flex-col overflow-hidden bg-canvas text-ink shadow-overlay sm:w-[420px] sm:border-s sm:border-hairline",
          closing ? "companion-out" : "companion-in",
        )}
      >
        <header className="companion-header relative shrink-0 overflow-hidden border-b border-hairline bg-surface-card px-4 pb-0 pt-[max(12px,env(safe-area-inset-top))] sm:px-5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span aria-hidden="true" className="companion-mini-orb inline-flex size-8 items-center justify-center rounded-pill bg-primary text-on-primary">
                <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 3.5c.7 4.4 2.6 6.3 7 7-4.4.7-6.3 2.6-7 7-.7-4.4-2.6-6.3-7-7 4.4-.7 6.3-2.6 7-7z" fill="currentColor" />
                </svg>
              </span>
              <div>
                <h2 id={`${id}-title`} className="font-display text-[20px] leading-tight text-ink">
                  Quarterly <em className="text-primary">companion</em>
                </h2>
              </div>
            </div>
            <button type="button" onClick={onClose} aria-label="Close the companion" className="inline-flex size-11 items-center justify-center rounded-pill text-ink hover:bg-surface-strong">
              <CloseIcon size={18} />
            </button>
          </div>
          <div role="tablist" aria-label="Companion" className="mt-2 flex gap-1">
            {tabs.map((t) => (
              <button
                key={t.key}
                id={`${id}-tab-${t.key}`}
                type="button"
                role="tab"
                aria-selected={tab === t.key}
                aria-controls={`${id}-panel`}
                tabIndex={tab === t.key ? 0 : -1}
                onClick={() => onTab(t.key)}
                onKeyDown={onTabKey}
                className={cn(
                  "relative inline-flex min-h-11 items-center gap-2 px-3 text-button transition-colors",
                  tab === t.key ? "text-ink after:absolute after:inset-x-3 after:bottom-0 after:h-[2px] after:rounded-pill after:bg-primary" : "text-muted hover:text-ink",
                )}
              >
                {t.label}
                {t.key === "foryou" && unread > 0 && (
                  <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-pill bg-primary px-1.5 text-[11px] font-semibold tabular-nums text-on-primary">
                    {unread > 9 ? "9+" : unread}
                    <span className="sr-only"> new</span>
                  </span>
                )}
              </button>
            ))}
          </div>
        </header>
        <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${tab}`} className="flex min-h-0 flex-1 flex-col">
          {children}
        </div>
      </div>
    </div>
  );
}
