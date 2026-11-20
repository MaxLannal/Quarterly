import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { CheckIcon, ErrorIcon, SparkIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { courseHref, isInternalPath, isTrustedExternal, Markdown } from "./markdown";
import type { AskCitation, AssistantTurn, TraceStep, Turn } from "./types";

const KIND_LABEL: Record<AskCitation["kind"], string> = {
  course: "Course",
  program: "Program",
  post: "Review",
  summary: "Students",
  attribute: "Data",
  thread: "Forum",
  guide: "Guide",
};

/** The live agent trace: each tool call appears with a spinner, then a check. */
export function AgentTrace({ steps, running, compact = false }: { steps: TraceStep[]; running: boolean; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  if (!running && steps.length === 0) return null;
  const list = (
    <ol className={cn("flex flex-col", compact ? "gap-1" : "gap-1.5")}>
      {steps.map((s, i) => (
        <li key={`${s.tool}-${i}`} className="ask-step flex items-center gap-2.5 text-caption text-body">
          <StepMark status={s.status} />
          <span className={cn(s.status === "started" && "text-ink", s.status === "failed" && "text-muted line-through decoration-muted/50")}>{s.label}</span>
        </li>
      ))}
      {running && (
        <li className="ask-step flex items-center gap-2.5 text-caption text-muted">
          <span aria-hidden="true" className="ask-thinking-dots inline-flex w-4 justify-center gap-[3px]">
            <i />
            <i />
            <i />
          </span>
          <span className="ask-shimmer">{steps.length ? "Putting it together" : "Thinking"}</span>
        </li>
      )}
    </ol>
  );
  if (running) {
    return (
      <div role="status" aria-live="polite" aria-label="What the guide is doing" className="mb-3">
        {list}
      </div>
    );
  }
  return (
    <div className="mb-3">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="-mx-2 inline-flex min-h-11 items-center gap-2 rounded-pill px-2 text-caption text-muted transition-colors hover:text-ink"
      >
        <span aria-hidden="true" className={cn("inline-block transition-transform", open && "rotate-90")}>
          ›
        </span>
        Looked at {steps.length} {steps.length === 1 ? "source" : "sources"}
      </button>
      {open && <div className="mt-1 border-s border-hairline ps-3">{list}</div>}
    </div>
  );
}

function StepMark({ status }: { status: TraceStep["status"] }) {
  if (status === "started") {
    return <span aria-hidden="true" className="ask-spinner inline-block size-4 shrink-0 rounded-pill border-[1.5px] border-primary/25 border-t-primary" />;
  }
  if (status === "failed") return <ErrorIcon size={16} className="shrink-0 text-muted" />;
  return (
    <span aria-hidden="true" className="ask-check inline-flex size-4 shrink-0 items-center justify-center rounded-pill bg-primary-wash text-primary">
      <CheckIcon size={11} strokeWidth={2.5} />
    </span>
  );
}

function ChipLink({ href, children, onNavigate, className }: { href: string; children: ReactNode; onNavigate?: () => void; className: string }) {
  if (isInternalPath(href)) {
    return (
      <Link to={href} onClick={onNavigate} className={className}>
        {children}
      </Link>
    );
  }
  if (isTrustedExternal(href)) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
        {children}
        <span aria-hidden="true" className="text-muted">
          ↗
        </span>
        <span className="sr-only"> (official page, opens in a new tab)</span>
      </a>
    );
  }
  return <span className={className}>{children}</span>;
}

const chipClass =
  "inline-flex min-h-9 max-w-full items-center gap-1.5 rounded-pill border border-hairline bg-surface-card px-3 py-1 text-caption text-body-strong transition-[border-color,background-color] hover:border-primary/40 hover:bg-primary-wash/50";

export function Citations({ citations, onNavigate }: { citations: AskCitation[]; onNavigate?: () => void }) {
  if (!citations.length) return null;
  return (
    <div className="mt-4">
      <p className="mb-2 text-caption-uppercase uppercase text-muted">Sources</p>
      <ul className="flex flex-wrap gap-1.5">
        {citations.map((c) => (
          <li key={`${c.kind}:${c.id}`} className="max-w-full">
            <ChipLink href={c.href} onNavigate={onNavigate} className={chipClass}>
              <span className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">{KIND_LABEL[c.kind]}</span>
              <span className="truncate">{c.label}</span>
            </ChipLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Courses({ turn, onNavigate, compact }: { turn: AssistantTurn; onNavigate?: () => void; compact: boolean }) {
  if (!turn.courses.length) return null;
  return (
    <div className="mt-4">
      <p className="mb-2 text-caption-uppercase uppercase text-muted">Courses in this answer</p>
      <ul className={cn("grid gap-1.5", !compact && "sm:grid-cols-2")}>
        {turn.courses.map((c) => (
          <li key={c.code} className="min-w-0">
            <Link
              to={courseHref(c.code)}
              onClick={onNavigate}
              className="group flex min-h-11 items-baseline gap-2 rounded-lg border border-hairline bg-canvas-soft px-3 py-2 transition-[border-color,background-color] hover:border-primary/40 hover:bg-surface-card"
            >
              <span className="shrink-0 text-caption font-semibold tabular-nums text-primary">{c.code}</span>
              <span className="truncate font-display text-[15px] font-semibold text-ink group-hover:underline group-hover:decoration-primary/40 group-hover:underline-offset-2">{c.title}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ActionButton({ label, onClick, pressed, children }: { label: string; onClick: () => void; pressed?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className={cn(
        "inline-flex size-11 items-center justify-center rounded-pill text-muted transition-colors hover:bg-surface-strong hover:text-ink",
        pressed && "bg-primary-wash text-primary hover:bg-primary-wash hover:text-primary",
      )}
    >
      {children}
    </button>
  );
}

const Thumb = ({ down = false }: { down?: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={down ? { transform: "rotate(180deg)" } : undefined}>
    <path d="M7 10v10H4V10h3zM7 10l4-7c1.7 0 2.6 1 2.3 2.7L12.7 9H18a2 2 0 012 2.3l-1.2 7A2 2 0 0116.8 20H7" />
  </svg>
);
const CopyGlyph = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="8.5" y="8.5" width="11" height="11" rx="2" />
    <path d="M15.5 8.5V6a1.5 1.5 0 00-1.5-1.5H6A1.5 1.5 0 004.5 6v8A1.5 1.5 0 006 15.5h2.5" />
  </svg>
);
const RetryGlyph = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M4.5 12a7.5 7.5 0 0113-5.1L19.5 9M19.5 4.5V9H15M19.5 12a7.5 7.5 0 01-13 5.1L4.5 15M4.5 19.5V15H9" />
  </svg>
);

export function AnswerBubble({
  turn,
  last,
  onRetry,
  onFollowup,
  onFeedback,
  onNavigate,
  compact = false,
}: {
  turn: AssistantTurn;
  last: boolean;
  onRetry: () => void;
  onFollowup: (q: string) => void;
  onFeedback: (v: "up" | "down" | null) => void;
  onNavigate?: () => void;
  compact?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const running = turn.status === "streaming";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(turn.text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };
  return (
    <article aria-busy={running} className="ask-answer flex gap-3 sm:gap-4">
      <span aria-hidden="true" className={cn("mt-0.5 inline-flex shrink-0 items-center justify-center rounded-pill bg-primary text-on-primary shadow-[0_0_0_4px_var(--color-primary-wash)]", compact ? "size-7" : "size-8")}>
        <SparkIcon size={compact ? 14 : 16} />
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="sr-only">Quarterly’s answer</h3>
        <AgentTrace steps={turn.steps} running={running} compact={compact} />
        {turn.status === "done" && (
          <>
            <Markdown
              text={turn.text}
              courses={turn.courses.map((c) => c.code)}
              onNavigate={onNavigate}
              className={cn("ask-prose text-body-strong", compact ? "text-body-sm leading-[1.6]" : "text-body-md leading-[1.7]")}
            />
            <Courses turn={turn} onNavigate={onNavigate} compact={compact} />
            <Citations
              citations={turn.citations.filter((c) => c.kind !== "course" || !turn.courses.some((x) => x.code === c.id))}
              onNavigate={onNavigate}
            />
            {last && turn.followups.length > 0 && (
              <div className="mt-5">
                <p className="mb-2 text-caption-uppercase uppercase text-muted">Ask next</p>
                <ul className="flex flex-col items-start gap-1.5">
                  {turn.followups.map((q) => (
                    <li key={q} className="max-w-full">
                      <button
                        type="button"
                        onClick={() => onFollowup(q)}
                        className="group inline-flex min-h-11 max-w-full items-center gap-2 rounded-pill border border-primary/20 bg-primary-wash/60 px-4 py-2 text-start text-caption text-primary transition-[background-color,border-color] hover:border-primary/40 hover:bg-primary-wash"
                      >
                        <span aria-hidden="true" className="transition-transform group-hover:translate-x-0.5">→</span>
                        <span>{q}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-4 flex flex-wrap items-center gap-x-1 gap-y-1 border-t border-hairline pt-2">
              <p className={cn("me-auto flex items-center gap-1.5 py-2 text-caption text-muted", compact ? "basis-full" : "basis-full sm:basis-auto")}>
                <SparkIcon size={13} />
                {turn.ai ? "Written by an AI and can be wrong." : "A plain search: the AI guide was resting."}
              </p>
              <ActionButton label={copied ? "Copied" : "Copy answer"} onClick={() => void copy()}>
                {copied ? <CheckIcon size={16} /> : <CopyGlyph />}
              </ActionButton>
              <ActionButton label="Ask again" onClick={onRetry}>
                <RetryGlyph />
              </ActionButton>
              <ActionButton label="Helpful" pressed={turn.feedback === "up"} onClick={() => onFeedback(turn.feedback === "up" ? null : "up")}>
                <Thumb />
              </ActionButton>
              <ActionButton label="Not helpful" pressed={turn.feedback === "down"} onClick={() => onFeedback(turn.feedback === "down" ? null : "down")}>
                <Thumb down />
              </ActionButton>
              <span className="sr-only" aria-live="polite">
                {copied ? "Answer copied" : ""}
              </span>
            </div>
          </>
        )}
        {(turn.status === "error" || turn.status === "stopped") && (
          <div role={turn.status === "error" ? "alert" : undefined} className="flex flex-wrap items-center gap-3 rounded-xl border border-hairline bg-surface-card px-4 py-3">
            <p className={cn("flex-1 text-caption", turn.status === "error" ? "text-error" : "text-muted")}>
              {turn.status === "error" ? turn.error || "Something went wrong." : "You stopped this answer."}
            </p>
            <button type="button" onClick={onRetry} className="inline-flex min-h-11 items-center gap-2 rounded-pill border border-hairline-strong px-4 text-button text-ink hover:bg-surface-strong">
              <RetryGlyph />
              Try again
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

export function UserBubble({ text, compact = false }: { text: string; compact?: boolean }) {
  return (
    <div className="ask-question flex justify-end">
      <h3 className="sr-only">You asked</h3>
      <p
        className={cn(
          "max-w-[85%] whitespace-pre-wrap break-words rounded-[22px] rounded-ee-md bg-ink text-on-dark",
          compact ? "px-3.5 py-2 text-body-sm" : "px-4 py-2.5 text-body-md",
        )}
      >
        {text}
      </p>
    </div>
  );
}

/** The turns of one conversation; scrolls a new question into view. */
export function TurnList({
  turns,
  onRetry,
  onFollowup,
  onFeedback,
  onNavigate,
  compact = false,
  scrollRoot,
}: {
  turns: Turn[];
  onRetry: (turnId: string) => void;
  onFollowup: (q: string) => void;
  onFeedback: (turnId: string, v: "up" | "down" | null) => void;
  onNavigate?: () => void;
  compact?: boolean;
  /** The scrolling element (the companion's panel); the window when absent. */
  scrollRoot?: HTMLElement | null;
}) {
  const lastUser = useRef<HTMLLIElement>(null);
  const count = turns.length;
  useEffect(() => {
    const el = lastUser.current;
    if (!el) return;
    const smooth = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (scrollRoot) {
      scrollRoot.scrollTo({ top: el.offsetTop - 12, behavior: smooth ? "smooth" : "auto" });
    } else {
      el.scrollIntoView?.({ block: "start", behavior: smooth ? "smooth" : "auto" });
    }
  }, [count, scrollRoot]);
  const lastUserIndex = turns.map((t) => t.role).lastIndexOf("user");
  const lastIndex = turns.length - 1;
  return (
    <ol className={cn("flex flex-col", compact ? "gap-5" : "gap-8")}>
      {turns.map((t, i) => (
        <li key={t.id} ref={i === lastUserIndex ? lastUser : undefined} className="scroll-mt-24">
          {t.role === "user" ? (
            <UserBubble text={t.text} compact={compact} />
          ) : (
            <AnswerBubble
              turn={t}
              last={i === lastIndex}
              compact={compact}
              onRetry={() => onRetry(t.id)}
              onFollowup={onFollowup}
              onFeedback={(v) => onFeedback(t.id, v)}
              onNavigate={onNavigate}
            />
          )}
        </li>
      ))}
    </ol>
  );
}
