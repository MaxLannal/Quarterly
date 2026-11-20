import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PlusIcon, SparkIcon } from "@/components/ui/icons";
import { useAuthLinks } from "@/features/auth/next";
import { Composer, type ComposerHandle } from "@/features/ask/Composer";
import { ASK_KEY, loadConversations, saveConversations } from "@/features/ask/conversations";
import { TurnList } from "@/features/ask/Thread";
import type { AskChat } from "@/features/ask/useAskChat";
import type { AskContext } from "@/features/ask/types";
import { suggestionsFor } from "./suggestions";

/**
 * The companion's chat: the Ask conversation in a compact form, sent with mode "companion" and
 * the page's context. "Open in Ask" hands the conversation to the Ask page.
 */
export function CompanionChat({
  chat,
  context,
  username,
  onNavigate,
  open,
}: {
  chat: AskChat;
  context: AskContext;
  username: string | null;
  onNavigate: () => void;
  open: boolean;
}) {
  const navigate = useNavigate();
  const links = useAuthLinks();
  const composer = useRef<ComposerHandle>(null);
  const [scroller, setScroller] = useState<HTMLDivElement | null>(null);
  const { lead, chips } = suggestionsFor(context);
  const turns = chat.active?.turns ?? [];

  useEffect(() => {
    if (!open) return;
    // Cancelled when the panel closes first, so a quick Escape keeps focus on the orb.
    const timer = window.setTimeout(() => composer.current?.focus(), 60);
    return () => window.clearTimeout(timer);
  }, [open]);

  const openInAsk = () => {
    const conv = chat.active;
    if (!conv) return;
    const stored = loadConversations(ASK_KEY).filter((c) => c.id !== conv.id);
    saveConversations(ASK_KEY, [{ ...conv, updatedAt: Date.now() }, ...stored]);
    onNavigate();
    navigate(`/ask?c=${encodeURIComponent(conv.id)}`);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={setScroller} className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-4 pt-5 sm:px-5">
        <div className="companion-greeting mb-5">
          <p className="font-display text-[26px] font-bold leading-[1.15] tracking-[-0.6px] text-ink">
            {username ? (
              <>
                Hi {username}. <em className="text-primary">What’s on your mind?</em>
              </>
            ) : (
              <>
                Hi. <em className="text-primary">What’s on your mind?</em>
              </>
            )}
          </p>
          <p className="mt-2 text-body-sm text-body">{lead}</p>
          <p className="mt-2 flex items-start gap-1.5 text-caption text-muted">
            <SparkIcon size={13} className="mt-[3px] shrink-0" />
            {username ? (
              <span>I know your interests from your dashboard, so my advice is about you.</span>
            ) : (
              <span>
                <Link to="/me" onClick={onNavigate} className="rounded-xs text-primary underline underline-offset-2">
                  Build a dashboard
                </Link>{" "}
                (or{" "}
                <Link to={links.login} onClick={onNavigate} className="rounded-xs text-primary underline underline-offset-2">
                  log in
                </Link>
                ) and I can tailor advice to you.
              </span>
            )}
          </p>
          {turns.length === 0 && (
            <ul className="mt-4 flex flex-col items-start gap-1.5">
              {chips.map((q, i) => (
                <li key={q} className="ask-chip max-w-full" style={{ animationDelay: `${80 + i * 60}ms` }}>
                  <button
                    type="button"
                    onClick={() => {
                      chat.send(q);
                      composer.current?.focus();
                    }}
                    className="inline-flex min-h-11 max-w-full items-center gap-2 rounded-pill border border-hairline-strong bg-surface-card px-3.5 py-2 text-start text-caption text-body-strong transition-colors hover:border-primary/40 hover:bg-primary-wash hover:text-primary"
                  >
                    <span aria-hidden="true" className="text-primary">
                      →
                    </span>
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {turns.length > 0 && (
          <TurnList
            compact
            turns={turns}
            scrollRoot={scroller}
            onRetry={chat.retry}
            onFollowup={chat.send}
            onFeedback={chat.setFeedback}
            onNavigate={onNavigate}
          />
        )}
      </div>
      <div className="border-t border-hairline bg-canvas/95 px-3 pb-[max(12px,env(safe-area-inset-bottom))] pt-3 sm:px-4">
        {turns.length > 0 && (
          <div className="mb-2 flex items-center justify-between gap-2">
            <button type="button" onClick={chat.newChat} className="inline-flex min-h-11 items-center gap-1.5 rounded-pill px-2.5 text-caption text-body hover:bg-surface-strong hover:text-ink">
              <PlusIcon size={14} />
              New chat
            </button>
            <button type="button" onClick={openInAsk} className="inline-flex min-h-11 items-center gap-1.5 rounded-pill px-2.5 text-caption text-primary hover:bg-primary-wash">
              Open in Ask
              <span aria-hidden="true">→</span>
            </button>
          </div>
        )}
        <Composer ref={composer} size="compact" onSend={chat.send} onStop={chat.stop} running={chat.running} placeholder="Ask the companion" label="Ask the companion" />
      </div>
    </div>
  );
}
