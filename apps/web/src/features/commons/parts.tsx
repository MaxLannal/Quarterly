/** Small pieces shared by the Commons pages: votes, handles, chips, the AI glyph, citations,
 * report and confirm dialogs, a toast, the login card and server-rendered bodies. */
import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type MouseEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ChoiceRow, Label, Textarea } from "@/components/ui/input";
import { ErrorText, Notice } from "@/components/ui/misc";
import { useAuthLinks } from "@/features/auth/next";
import { cn } from "@/lib/utils";
import { useReport, useVote, type Citation, type CourseRef, type TargetType, type VoteValue } from "./api";
import { proseClass } from "./markdown";
import { coursePath, dayWords, threadPath } from "./text";
import "@/features/courses/glass.css";

export const REPORT_REASONS = [
  "Personal attack or harassment",
  "Names or identifies a student",
  "Wrong or misleading information",
  "Spam or off topic",
  "Something else",
] as const;

// ----------------------------------------------------------------------------------- votes

function Chevron({ up }: { up: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={up ? "m6 15 6-6 6 6" : "m6 9 6 6 6-6"} />
    </svg>
  );
}

/**
 * Up/down votes with the net score. Pressing the same arrow again withdraws the vote. Logged
 * out, the arrows lead to the login page; on your own post they are disabled.
 */
export function VoteControl({
  targetType,
  targetId,
  score,
  myVote,
  mine,
  loggedIn,
  label,
  layout = "column",
  onScore,
}: {
  targetType: TargetType;
  targetId: number;
  score: number;
  myVote: VoteValue;
  mine: boolean;
  loggedIn: boolean;
  /** What is voted on, for screen readers ("the question", "Quiet Heron's answer"). */
  label: string;
  layout?: "column" | "row";
  onScore?: (score: number, myVote: VoteValue) => void;
}) {
  const [state, setState] = useState({ score, myVote });
  const [error, setError] = useState<string | null>(null);
  const vote = useVote();
  const authLinks = useAuthLinks();
  useEffect(() => setState({ score, myVote }), [score, myVote]);

  function cast(direction: 1 | -1) {
    const next: VoteValue = state.myVote === direction ? 0 : direction;
    const previous = state;
    setState({ score: state.score - state.myVote + next, myVote: next });
    setError(null);
    vote.mutate(
      { target_type: targetType, target_id: targetId, value: next },
      {
        onSuccess: (out) => {
          setState({ score: out.score, myVote: out.my_vote });
          onScore?.(out.score, out.my_vote);
        },
        onError: (e) => {
          setState(previous);
          setError(e.message);
        },
      },
    );
  }

  const arrow = (up: boolean) => {
    const pressed = state.myVote === (up ? 1 : -1);
    const cls = cn(
      "inline-flex size-11 items-center justify-center rounded-pill text-muted transition-colors hover:bg-surface-strong hover:text-ink",
      pressed && (up ? "bg-primary-wash text-primary hover:bg-primary-wash hover:text-primary" : "bg-surface-strong text-ink"),
    );
    const name = up ? "Upvote" : "Downvote";
    if (!loggedIn) {
      return (
        <Link to={authLinks.login} aria-label={`Log in to ${name.toLowerCase()} ${label}`} className={cls}>
          <Chevron up={up} />
        </Link>
      );
    }
    return (
      <button
        type="button"
        aria-label={`${name} ${label}`}
        aria-pressed={pressed}
        disabled={mine || vote.isPending}
        title={mine ? "You can't vote on your own post" : undefined}
        onClick={() => cast(up ? 1 : -1)}
        className={cn(cls, "disabled:cursor-not-allowed disabled:opacity-40")}
      >
        <Chevron up={up} />
      </button>
    );
  };

  return (
    <div className={cn("flex items-center", layout === "column" ? "flex-col" : "flex-row")}>
      {arrow(true)}
      <span
        className={cn(
          "min-w-6 text-center text-body-strong tabular-nums",
          state.myVote === 1 ? "text-primary" : "text-ink",
          layout === "column" ? "-my-1" : "",
        )}
        aria-live="polite"
      >
        <span className="sr-only">Score </span>
        {state.score}
      </span>
      {arrow(false)}
      {error && <span role="alert" className="sr-only">{error}</span>}
    </div>
  );
}

// --------------------------------------------------------------------------------- people

/** An author's handle with the OP and You marks. */
export function Handle({ handle, op, mine, className }: { handle: string; op?: boolean; mine?: boolean; className?: string }) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5", className)}>
      <span className="truncate font-medium text-ink">{handle}</span>
      {op && (
        <span title="Asked the question" className="rounded-pill bg-primary-wash px-2 py-px text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">
          OP
        </span>
      )}
      {mine && (
        <span className="rounded-pill bg-surface-strong px-2 py-px text-[11px] font-semibold uppercase tracking-[0.08em] text-ink">You</span>
      )}
    </span>
  );
}

export function Day({ day, edited }: { day: string; edited?: string | null }) {
  return (
    <span className="whitespace-nowrap font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
      {dayWords(day)}
      {edited ? <span title={`Edited ${dayWords(edited)}`}> · edited</span> : null}
    </span>
  );
}

// ---------------------------------------------------------------------------------- chips

export function CourseChip({ course, className }: { course: CourseRef; className?: string }) {
  return (
    <Link
      to={coursePath(course.code)}
      title={course.title}
      className={cn(
        "inline-flex min-h-8 max-w-full items-center gap-2 rounded-pill bg-[linear-gradient(90deg,rgb(255_92_112/0.16),rgb(255_92_112/0.04))] px-3 text-caption text-body shadow-[inset_0_0_0_1px_rgb(255_120_140/0.28)] transition-[color,box-shadow] duration-300 hover:text-ink hover:shadow-[inset_0_0_0_1px_rgb(255_120_140/0.6)]",
        "before:absolute before:inset-x-0 before:-inset-y-1.5 relative", // a 44px target on a 32px chip
        className,
      )}
    >
      <span className="font-mono text-[11.5px] font-medium uppercase tracking-[0.12em] text-ink">{course.code}</span>
      <span className="hidden truncate sm:inline">{course.title}</span>
    </Link>
  );
}

export function TagChip({ tag, to, active }: { tag: string; to?: string; active?: boolean }) {
  const cls = cn(
    "relative inline-flex min-h-8 items-center rounded-pill px-2.5 text-caption text-body before:absolute before:inset-x-0 before:-inset-y-1.5",
    active ? "bg-ink text-canvas" : "bg-white/[0.04] shadow-[inset_0_0_0_1px_rgb(255_255_255/0.09)] hover:text-ink hover:shadow-[inset_0_0_0_1px_rgb(255_255_255/0.2)]",
  );
  return to ? (
    <Link to={to} className={cls}>
      #{tag}
    </Link>
  ) : (
    <span className={cls}>#{tag}</span>
  );
}

/** Quarterly AI's mark: a small round arch (the chapel's window) with a spark. */
export function ArchGlyph({ size = 22, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <path d="M5 21V11a7 7 0 0 1 14 0v10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M9 21v-7a3 3 0 0 1 6 0v7" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.6" />
      <path d="M12 3.2c.25 1.6.9 2.25 2.5 2.5-1.6.25-2.25.9-2.5 2.5-.25-1.6-.9-2.25-2.5-2.5 1.6-.25 2.25-.9 2.5-2.5z" fill="currentColor" />
    </svg>
  );
}

function citationTarget(c: Citation): { to?: string; href?: string } {
  if (c.kind === "guide") return c.url && /^https:\/\//.test(c.url) ? { href: c.url } : {};
  if (c.url && c.url.startsWith("/")) return { to: c.url };
  if (c.kind === "course") return { to: coursePath(c.id) };
  if (c.kind === "attribute") return { to: coursePath(c.id.split(":")[0] ?? c.id) };
  if (c.kind === "program") return { to: `/programs/${encodeURIComponent(c.id)}` };
  if (c.kind === "thread" && /^\d+$/.test(c.id)) return { to: threadPath(Number(c.id)) };
  return {};
}

const KIND_LABEL: Record<Citation["kind"], string> = {
  course: "Course",
  program: "Program",
  thread: "Question",
  guide: "Campus guide",
  post: "Review",
  summary: "Reviews",
  attribute: "Data",
};

/** The bot's sources as chips: courses, programs, questions, reviews and the campus guide. */
export function CitationChips({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <p className="qg-kicker">Sources</p>
      <ul className="flex flex-wrap gap-2">
        {citations.map((c) => {
          const target = citationTarget(c);
          const inner = (
            <>
              <span className="font-mono text-[10.5px] font-medium uppercase tracking-[0.16em] text-muted">{KIND_LABEL[c.kind]}</span>
              <span className="min-w-0 truncate">{c.label}</span>
              {target.href && (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
                </svg>
              )}
            </>
          );
          const cls =
            "inline-flex min-h-11 max-w-full items-center gap-2 rounded-pill bg-white/[0.04] px-3.5 text-caption text-ink shadow-[inset_0_0_0_1px_rgb(255_255_255/0.1),inset_0_1px_0_rgb(255_255_255/0.08)] transition-[color,box-shadow] duration-300 hover:text-primary-hover hover:shadow-[inset_0_0_0_1px_rgb(255_120_140/0.5)]";
          return (
            <li key={`${c.kind}:${c.id}`} className="max-w-full">
              {target.to ? (
                <Link to={target.to} className={cls}>
                  {inner}
                </Link>
              ) : target.href ? (
                <a href={target.href} target="_blank" rel="noopener noreferrer" className={cls}>
                  {inner}
                  <span className="sr-only">(opens uchicago.edu in a new tab)</span>
                </a>
              ) : (
                <span className={cls}>{inner}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------------- bodies

/**
 * A server-rendered, server-sanitized body (nh3 allow-list, see api/forum/markdown.py). Links to
 * this site (course mentions) navigate inside the app; others open in a new tab.
 */
export function Body({ html, className }: { html: string; className?: string }) {
  const navigate = useNavigate();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelectorAll<HTMLAnchorElement>("a[href^='http']").forEach((a) => {
      a.target = "_blank";
    });
  }, [html]);
  function onClick(e: MouseEvent<HTMLDivElement>) {
    const a = (e.target as HTMLElement).closest("a");
    const href = a?.getAttribute("href");
    if (!a || !href || !href.startsWith("/") || href.startsWith("//")) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(href);
  }
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- delegates clicks on the links inside; links are keyboard-reachable themselves
    <div
      ref={ref}
      onClick={onClick}
      className={cn(proseClass, className)}
      // Sanitized on the server (tag allow-list, no raw HTML, http(s) links only).
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

// ----------------------------------------------------------------------------------- toast

export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const show = useCallback((text: string) => {
    setMessage(text);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setMessage(null), 2600);
  }, []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const node = (
    <div aria-live="polite" role="status" className="pointer-events-none fixed inset-x-0 bottom-6 z-40 flex justify-center px-4">
      {message && (
        <p className="glass-raised pointer-events-auto animate-rise rounded-pill px-5 py-3 text-body-sm text-ink">{message}</p>
      )}
    </div>
  );
  return { show, node };
}

// ---------------------------------------------------------------------------------- dialogs

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  onConfirm,
  onClose,
  pending,
  error,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  pending?: boolean;
  error?: string | null;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title} description={description}>
      {error && <ErrorText className="mb-3">{error}</ErrorText>}
      <div className="flex flex-wrap justify-end gap-3">
        <Button variant="outline" onClick={onClose}>
          Keep it
        </Button>
        <Button variant="destructive" onClick={onConfirm} disabled={pending}>
          {pending ? "Deleting…" : confirmLabel}
        </Button>
      </div>
    </Dialog>
  );
}

export function ReportDialog({
  open,
  onClose,
  targetType,
  targetId,
}: {
  open: boolean;
  onClose: () => void;
  targetType: TargetType;
  targetId: number;
}) {
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const report = useReport();
  const id = useId();

  function close() {
    setReason("");
    setDetails("");
    setProblem(null);
    report.reset();
    onClose();
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!reason) {
      setProblem("Choose a reason.");
      return;
    }
    setProblem(null);
    const text = details.trim() ? `${reason}: ${details.trim()}` : reason;
    report.mutate({ target_type: targetType, target_id: targetId, reason: text.slice(0, 500) });
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title={targetType === "thread" ? "Report this question" : "Report this reply"}
      description="Moderators read every report. Nobody is told who reported it."
    >
      {report.isSuccess ? (
        <div className="flex flex-col gap-4">
          <Notice tone="success" role="status">
            Thanks. A moderator will look at it.
          </Notice>
          <div>
            <Button variant="outline" onClick={close}>
              Close
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <fieldset className="flex flex-col">
            <legend className="mb-1 text-caption font-medium text-ink">Reason</legend>
            {REPORT_REASONS.map((r) => (
              <ChoiceRow key={r} type="radio" name={`${id}-reason`} value={r} checked={reason === r} onChange={() => setReason(r)}>
                {r}
              </ChoiceRow>
            ))}
          </fieldset>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`${id}-details`}>Details (optional)</Label>
            <Textarea id={`${id}-details`} rows={3} maxLength={400} value={details} onChange={(e) => setDetails(e.target.value)} />
          </div>
          {problem && <ErrorText>{problem}</ErrorText>}
          {report.error && <ErrorText>{report.error.message}</ErrorText>}
          <div className="flex flex-wrap justify-end gap-3">
            <Button type="button" variant="outline" onClick={close}>
              Cancel
            </Button>
            <Button type="submit" disabled={report.isPending}>
              {report.isPending ? "Sending…" : "Send report"}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

// ---------------------------------------------------------------------------------- login

export function LoginCard({ children, className }: { children?: ReactNode; className?: string }) {
  const links = useAuthLinks();
  return (
    <div className={cn("flex flex-col items-start gap-3 qg-tile px-6 py-6 sm:flex-row sm:items-center sm:justify-between", className)}>
      <p className="text-body-sm text-body">
        {children ?? "Log in to answer. Your name never shows: you get a random handle on each question."}
      </p>
      <div className="flex shrink-0 gap-2">
        <Button asChild>
          <Link to={links.login}>Log in</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to={links.signup}>Sign up</Link>
        </Button>
      </div>
    </div>
  );
}

/** The three dots of "is typing". Static under reduced motion (index.css stops animations). */
export function TypingDots() {
  return (
    <span aria-hidden="true" className="inline-flex items-center gap-[3px]">
      {[0, 1, 2].map((i) => (
        <span key={i} className="inline-block size-1.5 animate-typing rounded-pill bg-primary" style={{ animationDelay: `${i * 160}ms` }} />
      ))}
    </span>
  );
}
