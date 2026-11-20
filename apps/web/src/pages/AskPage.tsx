import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { TypeHero } from "@/components/brand/TypeHero";
import { TypeScape } from "@/components/brand/TypeScape";
import { useFocusTrap } from "@/components/ui/dialog";
import { CloseIcon, MenuIcon, PlusIcon, SparkIcon } from "@/components/ui/icons";
import { Composer, type ComposerHandle } from "@/features/ask/Composer";
import { ConversationList } from "@/features/ask/ConversationList";
import { ASK_KEY, loadConversations } from "@/features/ask/conversations";
import { TurnList } from "@/features/ask/Thread";
import { useAskChat } from "@/features/ask/useAskChat";
import "@/features/ask/ask.css";
import { useMediaQuery, usePresence } from "@/lib/motion";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "Which Core humanities sequence suits someone who loves film?",
  "How do I get into quantum computing research as a first-year?",
  "What do students say about MATH 15100?",
  "What's the difference between the CS BA and BS?",
  "Where are the best places to study on campus?",
  "How does study abroad fit with the Core?",
];

const SOURCES = [
  { title: "The 2026-27 catalog", text: "Every course, its prerequisites and when it usually runs." },
  { title: "Majors and minors", text: "Requirements of the programs Quarterly holds, quoted from the catalog." },
  { title: "What students say", text: "Reviews and forum questions from UChicago students (after you log in)." },
  { title: "The campus guide", text: "Short notes on the Core, advising, libraries and life in the College, with official links." },
];

/**
 * Ask (docs/BEST-OF-UCHICAGO-PLAN.md): the campus chatbot. First visit: the Gothic-window hero
 * with the question box and example questions. A conversation: a slim arch band, the
 * conversation column with the live agent trace, and the question box pinned below. `?q=` (the
 * homepage's question bar) starts a new conversation with that question; `?c=` opens one the
 * companion handed over.
 */
export default function AskPage() {
  const chat = useAskChat({ storageKey: ASK_KEY, mode: "ask" });
  const [params, setParams] = useSearchParams();
  const handled = useRef(false);
  const composer = useRef<ComposerHandle>(null);
  const [drawer, setDrawer] = useState(false);
  // A logged-in question needs the session's CSRF token: wait until the session is known.
  const sessionLoading = useSession().isLoading;

  useEffect(() => {
    if (handled.current || sessionLoading) return;
    const q = params.get("q")?.trim();
    const c = params.get("c");
    if (!q && !c) return;
    handled.current = true;
    if (c && loadConversations(ASK_KEY).some((x) => x.id === c)) chat.select(c);
    else if (q) chat.send(q);
    const next = new URLSearchParams(params);
    next.delete("q");
    next.delete("c");
    setParams(next, { replace: true });
  }, [params, setParams, chat, sessionLoading]);

  // A question asked from the landing (a chip, the hero box) swaps the layout: keep the
  // keyboard in the question box of the conversation.
  const activeId = chat.activeId;
  useEffect(() => {
    if (activeId && (document.activeElement === document.body || !document.activeElement)) composer.current?.focus();
  }, [activeId]);

  useEffect(() => {
    const title = chat.active ? `${chat.active.title} · Ask Quarterly` : "Ask Quarterly";
    document.title = title;
    return () => {
      document.title = "Quarterly";
    };
  }, [chat.active]);

  const list = (
    <ConversationList
      conversations={chat.conversations}
      activeId={chat.activeId}
      onSelect={(id) => {
        chat.select(id);
        setDrawer(false);
      }}
      onNew={() => {
        chat.newChat();
        setDrawer(false);
      }}
      onRename={chat.rename}
      onDelete={chat.remove}
      onClear={() => {
        chat.clearAll();
        setDrawer(false);
      }}
    />
  );

  if (!chat.active || chat.active.turns.length === 0) {
    return <AskLanding onAsk={chat.send} recent={chat.conversations.slice(0, 6)} onOpen={chat.select} composerRef={composer} />;
  }

  return (
    <div className="relative">
      <section className="relative isolate h-[124px] overflow-hidden border-b border-hairline sm:h-[144px]">
        <TypeScape shape="arch" focus={0.86} label="A Gothic window drawn with the titles of real courses" />
        <div aria-hidden="true" className="ask-band-veil pointer-events-none absolute inset-0 -z-10" />
        <div className="mx-auto flex h-full w-full max-w-content items-end justify-between gap-3 px-4 pb-4 sm:px-6 sm:pb-5 lg:px-8">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-caption-uppercase uppercase text-primary">
              <span aria-hidden="true" className="inline-block h-px w-6 bg-primary" />
              Ask Quarterly
            </p>
            <h1 className="mt-1.5 truncate font-display text-[26px] font-bold leading-tight tracking-[-0.4px] text-ink sm:text-[32px]">{chat.active.title}</h1>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setDrawer(true)}
              className="inline-flex min-h-11 items-center gap-2 rounded-pill border border-hairline-strong bg-surface-card/90 px-3.5 text-button text-ink hover:bg-surface-strong lg:hidden"
              aria-haspopup="dialog"
            >
              <MenuIcon size={16} />
              <span className="max-[420px]:sr-only">Conversations</span>
            </button>
            <button
              type="button"
              onClick={chat.newChat}
              className="inline-flex min-h-11 items-center gap-2 rounded-pill border border-hairline-strong bg-surface-card/90 px-3.5 text-button text-ink hover:bg-surface-strong"
            >
              <PlusIcon size={16} />
              <span className="max-[420px]:sr-only">New</span>
            </button>
          </div>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-content gap-10 px-4 sm:px-6 lg:px-8">
        <aside className="hidden w-[248px] shrink-0 lg:block">
          <div className="sticky top-4 max-h-[calc(100svh-32px)] overflow-y-auto py-8 pe-1">{list}</div>
        </aside>
        <div className="flex min-h-[calc(100svh-200px)] min-w-0 flex-1 flex-col">
          <div className="mx-auto w-full max-w-[760px] flex-1 pb-6 pt-8">
            <h2 className="sr-only">Conversation</h2>
            <TurnList
              turns={chat.active.turns}
              onRetry={chat.retry}
              onFollowup={chat.send}
              onFeedback={chat.setFeedback}
            />
          </div>
          <div className="sticky bottom-0 z-10 mx-auto w-full max-w-[760px] bg-[linear-gradient(to_top,var(--color-canvas)_72%,transparent)] pb-[max(14px,env(safe-area-inset-bottom))] pt-6">
            <Composer ref={composer} onSend={chat.send} onStop={chat.stop} running={chat.running} placeholder="Ask a follow-up" label="Your next question" />
            <p className="mt-2 hidden text-center text-caption text-muted sm:block">
              Enter to send, Shift+Enter for a new line. Answers are written by an AI and can be wrong.
            </p>
          </div>
        </div>
      </div>
      <Drawer open={drawer} onClose={() => setDrawer(false)}>
        {list}
      </Drawer>
    </div>
  );
}

function AskLanding({
  onAsk,
  recent,
  onOpen,
  composerRef,
}: {
  onAsk: (q: string) => void;
  recent: { id: string; title: string; turns: unknown[] }[];
  onOpen: (id: string) => void;
  composerRef: React.RefObject<ComposerHandle>;
}) {
  const wide = useMediaQuery("(min-width: 900px)");
  const session = useSession();
  return (
    <>
      <TypeHero
        shape="arch"
        tall
        label="A Gothic window drawn with the titles of real courses"
        kicker="Ask Quarterly"
        title={
          <>
            Ask <em>anything</em> about UChicago.
          </>
        }
        subline="Courses, the Core, majors and minors, what students say, life in the College. The guide looks it up, shows its sources and links every course."
      >
        <Composer ref={composerRef} size="hero" onSend={onAsk} focusOnMount={wide} placeholder="Ask about a course, the Core, a major…" />
        <div>
          <p className="mb-2.5 text-caption-uppercase uppercase text-muted">Try asking</p>
          <ul className="flex flex-wrap gap-2">
            {EXAMPLES.map((q, i) => (
              <li key={q} className="ask-chip max-w-full" style={{ animationDelay: `${120 + i * 70}ms` }}>
                <button
                  type="button"
                  onClick={() => onAsk(q)}
                  className="min-h-11 max-w-full rounded-pill border border-hairline-strong bg-surface-card/90 px-4 py-2 text-start text-caption text-body-strong shadow-[0_1px_0_rgba(0,0,0,0.02)] backdrop-blur-[2px] transition-[border-color,background-color,color] hover:border-primary/40 hover:bg-primary-wash hover:text-primary"
                >
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </TypeHero>

      <div className="mx-auto w-full max-w-content px-4 py-14 sm:px-6 lg:px-8">
        <div className={cn("grid gap-12", recent.length > 0 && "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]")}>
          <section aria-labelledby="ask-reads">
            <h2 id="ask-reads" className="font-display text-display-sm text-ink">
              What the guide <em className="text-primary">reads</em>
            </h2>
            <ol className="mt-6 grid gap-x-8 gap-y-6 sm:grid-cols-2">
              {SOURCES.map((s, i) => (
                <li key={s.title} className="border-t border-hairline pt-4">
                  <p className="font-serif text-[16px] italic text-primary">{["i.", "ii.", "iii.", "iv."][i]}</p>
                  <h3 className="mt-1 text-body-strong text-ink">{s.title}</h3>
                  <p className="mt-1 text-body-sm text-body">{s.text}</p>
                </li>
              ))}
            </ol>
            <p className="mt-8 flex items-start gap-2 text-caption text-muted">
              <SparkIcon size={14} className="mt-[3px] shrink-0" />
              <span>
                Answers are written by an AI and can be wrong; the catalog and your College adviser have the last word.
                {session.data ? " The guide knows what you told your dashboard." : " "}
                {!session.data && (
                  <>
                    <Link to="/me" className="rounded-xs text-primary underline underline-offset-2">
                      Build your dashboard
                    </Link>{" "}
                    and it can tailor answers to you.
                  </>
                )}
              </span>
            </p>
          </section>
          {recent.length > 0 && (
            <section aria-labelledby="ask-recent">
              <h2 id="ask-recent" className="font-display text-display-sm text-ink">
                Pick up <em className="text-primary">where you left off</em>
              </h2>
              <ul className="mt-6 flex flex-col">
                {recent.map((c) => (
                  <li key={c.id} className="border-t border-hairline">
                    <button
                      type="button"
                      onClick={() => onOpen(c.id)}
                      className="group flex min-h-14 w-full items-center justify-between gap-4 py-3 text-start"
                    >
                      <span className="min-w-0 truncate text-body-md text-ink group-hover:text-primary">{c.title}</span>
                      <span className="shrink-0 text-caption text-muted">
                        {Math.ceil(c.turns.length / 2)} {Math.ceil(c.turns.length / 2) === 1 ? "question" : "questions"}
                        <span aria-hidden="true" className="ms-2 inline-block transition-transform group-hover:translate-x-0.5">
                          →
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </>
  );
}

/** The conversations drawer on phones: from the left, focus trapped, Escape closes. */
function Drawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const presence = usePresence(open);
  useFocusTrap(ref, open, onClose);
  if (presence === "closed") return null;
  const closing = presence === "closing";
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- Escape and the Close button are the keyboard path
    <div
      className={cn("fixed inset-0 z-50 lg:hidden", closing ? "bg-ink/0 transition-colors duration-200" : "animate-fade-in bg-ink/40")}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label="Conversations"
        className={cn(
          "flex h-full w-[min(86vw,340px)] flex-col gap-4 overflow-y-auto bg-canvas p-4 pt-3 shadow-overlay",
          closing ? "ask-drawer-out" : "ask-drawer-in",
        )}
      >
        <div className="flex items-center justify-between">
          <p className="font-display text-title-md text-ink">Conversations</p>
          <button type="button" onClick={onClose} aria-label="Close" className="inline-flex size-11 items-center justify-center rounded-pill text-ink hover:bg-surface-strong">
            <CloseIcon size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
