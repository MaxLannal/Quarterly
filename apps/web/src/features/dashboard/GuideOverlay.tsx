import { Fragment, useEffect, useId, useMemo, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useFocusTrap } from "@/components/ui/dialog";
import { CheckIcon, CloseIcon, SendIcon } from "@/components/ui/icons";
import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { Profile, Topic } from "./api";
import { answeredTopics, courseHref, filledTopics, ownWords, seeded, TOPIC_LABELS, TOPICS, type Fact } from "./logic";
import { GuideMark } from "./parts";
import type { Guide } from "./useGuide";

/** Quick replies that are actions on the page rather than answers. */
export function isDraftChip(text: string): boolean {
  return /draft (my |some |a few )?routes?/i.test(text);
}

/**
 * The guide, immersive: a full-screen ink room with the student's own words drifting behind the
 * question, which appears word by word in large Newsreader. Quick replies, a composer, the live
 * trace of what the guide is reading, a rail of topics, and "Noted" chips the student keeps or
 * drops (kept facts are saved at once and the dashboard behind updates). Escape closes.
 */
export function GuideOverlay({ open, onClose, guide, profile, onDraftRoutes }: { open: boolean; onClose: () => void; guide: Guide; profile: Profile; onDraftRoutes: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const [draft, setDraft] = useState("");
  useFocusTrap(ref, open, onClose, composer);

  useEffect(() => {
    if (!open) return;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [open]);

  // Back to the composer once the guide answers.
  const answered = guide.status === "idle" && !!guide.current;
  const currentText = guide.current?.text;
  useEffect(() => {
    if (open && answered) composer.current?.focus({ preventScroll: true });
  }, [open, answered, currentText]);

  if (!open) return null;
  const turn = guide.current;
  const thinking = guide.status === "thinking";
  const covered = new Set<Topic>([...filledTopics(profile), ...profile.interview.covered, ...answeredTopics(guide.turns)]);
  const lastStudent = guide.pending ?? [...guide.turns].reverse().find((t) => t.role === "student")?.text ?? null;

  function send(text: string) {
    if (isDraftChip(text)) {
      onDraftRoutes();
      return;
    }
    guide.reply(text);
    setDraft("");
  }

  return createPortal(
    <div
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-[60] flex animate-fade-in flex-col overflow-y-auto overscroll-contain bg-surface-dark text-on-dark"
    >
      <DriftingWords words={ownWords(profile, guide.kept.map((f) => f.value))} />
      <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-on-dark/10 bg-surface-dark/85 px-4 py-2 backdrop-blur sm:px-8">
        <GuideMark size={18} className={cn("text-primary", thinking && "dash-thinking")} />
        <h2 id={titleId} className="font-display text-title-md text-on-dark">
          Your guide
        </h2>
        <ProgressRail current={turn?.topic ?? null} covered={covered} progress={turn?.progress ?? covered.size / 7} />
        <button
          type="button"
          onClick={onClose}
          className="ml-auto inline-flex min-h-11 items-center gap-2 rounded-pill px-3 text-button text-on-dark hover:bg-on-dark/10"
          aria-label="Close the guide and go back to your dashboard"
        >
          <span className="hidden sm:inline">Back to your dashboard</span>
          <CloseIcon size={18} />
        </button>
      </header>
      <div aria-hidden="true" className="sticky top-[61px] z-10 h-0.5 w-full bg-on-dark/10 md:hidden">
        <div className="h-full bg-primary transition-[width] duration-700" style={{ width: `${Math.round((turn?.progress ?? covered.size / 7) * 100)}%` }} />
      </div>

      <div className="relative mx-auto grid w-full max-w-[1200px] flex-1 gap-8 px-4 pb-16 pt-8 sm:px-8 lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-12 lg:pt-14">
        <div className="flex min-w-0 flex-col gap-6">
          {lastStudent && (
            <p className="max-w-[46rem] text-body-sm text-on-dark-soft">
              <span className="text-caption-uppercase uppercase">You said</span> <span className="italic">“{lastStudent.length > 220 ? `${lastStudent.slice(0, 220)}…` : lastStudent}”</span>
            </p>
          )}

          <div className="min-h-[9rem]">
            {turn && !thinking ? (
              <>
                <Question key={turn.text} text={turn.text} />
                <p aria-live="polite" className="sr-only">
                  {turn.text}
                </p>
              </>
            ) : thinking ? (
              <Thinking steps={guide.steps} />
            ) : guide.status === "error" ? null : (
              <Thinking steps={[]} />
            )}
          </div>

          {guide.status === "error" && (
            <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-on-dark/15 bg-surface-dark-elevated px-4 py-3 text-body-sm">
              <span className="min-w-0 flex-1">{guide.error}</span>
              <button type="button" onClick={guide.retry} className="min-h-11 rounded-pill bg-on-dark px-4 text-button text-ink hover:bg-on-dark-soft">
                Try again
              </button>
            </div>
          )}

          {turn && !thinking && turn.courses.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="Courses your guide mentioned">
              {turn.courses.map((c) => (
                <li key={c.code}>
                  <Link to={courseHref(c.code)} onClick={onClose} className="inline-flex min-h-11 items-center gap-2 rounded-pill border border-on-dark/25 px-4 text-body-sm text-on-dark hover:bg-on-dark/10">
                    <span className="font-sans text-caption-uppercase uppercase tabular-nums text-on-dark-soft">{c.code}</span>
                    <span className="max-w-[18rem] truncate">{c.title}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {turn && !thinking && turn.quick_replies.length > 0 && (
            <div className="flex flex-wrap gap-2" role="group" aria-label="Quick answers">
              {turn.quick_replies.map((q, i) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => send(q)}
                  style={{ "--delay": `${200 + i * 50}ms` } as CSSProperties}
                  className={cn(
                    "dash-rise min-h-11 rounded-pill border px-4 text-body-sm transition-colors",
                    isDraftChip(q) ? "border-primary bg-primary text-on-primary hover:bg-primary-hover" : "border-on-dark/25 text-on-dark hover:border-on-dark/60 hover:bg-on-dark/10",
                  )}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {turn?.done && !thinking && (
            <div className="dash-rise flex flex-wrap items-center gap-3 rounded-xl border border-on-dark/15 bg-surface-dark-elevated p-4">
              <p className="min-w-0 flex-1 text-body-sm text-on-dark">That's the whole conversation. Keep the notes that ring true; your portrait waits on the dashboard.</p>
              <button type="button" onClick={onDraftRoutes} className="min-h-11 rounded-pill bg-primary px-5 text-button text-on-primary hover:bg-primary-hover">
                Draft my routes
              </button>
              <button type="button" onClick={onClose} className="min-h-11 rounded-pill px-4 text-button text-on-dark hover:bg-on-dark/10">
                Back to your dashboard
              </button>
            </div>
          )}

          <form
            className="flex items-end gap-2 rounded-xxl border border-on-dark/20 bg-surface-dark-elevated p-2 focus-within:border-on-dark/50"
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
          >
            <label htmlFor={`${titleId}-answer`} className="sr-only">
              Your answer
            </label>
            <textarea
              id={`${titleId}-answer`}
              ref={composer}
              rows={2}
              maxLength={2000}
              value={draft}
              disabled={thinking}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  if (draft.trim()) send(draft);
                }
              }}
              placeholder={thinking ? "Your guide is thinking…" : "Answer in your own words…"}
              className="min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-body-md text-on-dark outline-none placeholder:text-on-dark-soft disabled:opacity-60"
            />
            <button type="submit" disabled={thinking || !draft.trim()} aria-label="Send your answer" className="inline-flex size-11 shrink-0 items-center justify-center rounded-pill bg-primary text-on-primary hover:bg-primary-hover disabled:bg-on-dark/15 disabled:text-on-dark-soft">
              <SendIcon size={18} />
            </button>
          </form>
          <p className="text-caption text-on-dark-soft">
            {turn?.fallback ? "Your guide is running without the AI right now; it asks the same questions." : "Your guide is an AI and can be wrong."} Nothing is saved to your portrait unless you keep it. Enter sends, Shift+Enter starts a new line.
          </p>
        </div>

        <aside aria-label="Noted" className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
          <NotedPanel guide={guide} />
        </aside>
      </div>
    </div>,
    document.body,
  );
}

function Question({ text }: { text: string }) {
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <p aria-hidden="true" className="max-w-[46rem] font-display text-[28px] font-light leading-[1.18] tracking-[-0.3px] text-on-dark text-balance sm:text-[40px] sm:leading-[1.12]">
      {words.map((w, i) => (
        <Fragment key={i}>
          <span className="dash-word" style={{ "--i": Math.min(i, 60) } as CSSProperties}>
            {w}
          </span>
          {i < words.length - 1 ? " " : ""}
        </Fragment>
      ))}
    </p>
  );
}

function Thinking({ steps }: { steps: Guide["steps"] }) {
  // One line per tool: its latest status.
  const latest = new Map<string, Guide["steps"][number]>();
  for (const s of steps) latest.set(`${s.tool}:${s.label}`, s);
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3">
      <p className="flex items-center gap-3 font-display text-[26px] font-light italic text-on-dark-soft sm:text-[32px]">
        <GuideMark size={20} className="dash-thinking text-primary" />
        Your guide is thinking…
      </p>
      {latest.size > 0 && (
        <ul className="flex flex-col gap-1.5 text-body-sm text-on-dark-soft">
          {[...latest.values()].map((s) => (
            <li key={`${s.tool}:${s.label}`} className="dash-rise flex items-center gap-2">
              <span aria-hidden="true" className={cn("inline-flex size-4 items-center justify-center", s.status === "done" ? "text-success" : s.status === "failed" ? "text-error" : "")}>
                {s.status === "done" ? <CheckIcon size={14} /> : s.status === "failed" ? <CloseIcon size={14} /> : <span className="inline-block size-1.5 animate-pulse rounded-pill bg-on-dark" />}
              </span>
              {s.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ProgressRail({ current, covered, progress }: { current: Topic | null; covered: Set<Topic>; progress: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, progress)) * 100);
  return (
    <div className="ml-2 hidden min-w-0 flex-1 items-center gap-3 md:flex" aria-label={`Conversation ${pct}% done`} role="group">
      <ol className="flex min-w-0 items-center gap-1">
        {TOPICS.map((t) => {
          const isCurrent = t === current;
          const done = covered.has(t) && !isCurrent;
          return (
            <li key={t} className="flex items-center gap-1" aria-current={isCurrent ? "step" : undefined}>
              <span
                className={cn(
                  "inline-flex min-h-7 items-center rounded-pill px-2.5 text-[12px] font-medium",
                  isCurrent ? "bg-primary text-on-primary" : done ? "text-on-dark" : "text-on-dark-soft/70",
                )}
              >
                {done && <CheckIcon size={11} className="mr-1 text-success" />}
                {TOPIC_LABELS[t]}
              </span>
            </li>
          );
        })}
      </ol>
      <span className="text-caption tabular-nums text-on-dark-soft">{pct}%</span>
    </div>
  );
}

function NotedPanel({ guide }: { guide: Guide }) {
  const { facts, kept } = guide;
  return (
    <div className="flex flex-col gap-3 rounded-xxl border border-on-dark/15 bg-surface-dark-elevated/70 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-display text-title-md text-on-dark">Noted</h3>
        {facts.length > 1 && (
          <button type="button" onClick={guide.keepEverything} className="min-h-11 rounded-pill px-3 text-button text-on-dark underline underline-offset-4 hover:bg-on-dark/10">
            Keep all
          </button>
        )}
      </div>
      {facts.length === 0 && kept.length === 0 && <p className="text-body-sm text-on-dark-soft">What you tell your guide shows up here. Keep what's right; drop the rest.</p>}
      {facts.length > 0 && (
        <ul className="flex flex-col gap-2">
          {facts.map((f) => (
            <NotedChip key={f.id} fact={f} onKeep={() => guide.keep(f)} onDrop={() => guide.drop(f)} />
          ))}
        </ul>
      )}
      {kept.length > 0 && (
        <div>
          <p className="mb-1.5 text-caption-uppercase uppercase text-on-dark-soft">Kept in your portrait</p>
          <ul className="flex flex-wrap gap-1.5">
            {kept.map((f) => (
              <li key={f.id} className="inline-flex max-w-full items-center gap-1 rounded-pill bg-primary/80 px-3 py-1 text-caption text-on-primary">
                <CheckIcon size={12} /> <span className="truncate">{f.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function NotedChip({ fact, onKeep, onDrop }: { fact: Fact; onKeep: () => void; onDrop: () => void }) {
  return (
    <li className="dash-rise flex items-center gap-1 rounded-xl border border-on-dark/15 bg-surface-dark px-3 py-1.5">
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-on-dark-soft">{fact.label}</p>
        <p className="line-clamp-3 text-body-sm text-on-dark">{fact.value}</p>
      </div>
      <button type="button" onClick={onKeep} aria-label={`Keep ${fact.label}: ${fact.value}`} className="inline-flex size-11 shrink-0 items-center justify-center rounded-pill text-success hover:bg-on-dark/10">
        <CheckIcon size={18} />
      </button>
      <button type="button" onClick={onDrop} aria-label={`Drop ${fact.label}: ${fact.value}`} className="inline-flex size-11 shrink-0 items-center justify-center rounded-pill text-on-dark-soft hover:bg-on-dark/10 hover:text-on-dark">
        <CloseIcon size={16} />
      </button>
    </li>
  );
}

/** The student's own words, drifting slowly behind the conversation (still under reduced motion). */
function DriftingWords({ words }: { words: string[] }) {
  const placed = useMemo(() => {
    const rnd = seeded(words.length * 7919 + 13);
    const still = prefersReducedMotion();
    const list = words.length ? words : ["curiosity", "the Core", "a question", "Hyde Park", "the quarter"];
    return Array.from({ length: Math.min(16, Math.max(8, list.length * 2)) }, (_, i) => ({
      word: list[i % list.length] as string,
      left: `${4 + rnd() * 84}%`,
      top: `${6 + rnd() * 86}%`,
      size: 18 + Math.round(rnd() * 40),
      o: 0.05 + rnd() * 0.1,
      d: still ? 0 : 40 + rnd() * 60,
      dx: `${Math.round(-70 + rnd() * 140)}px`,
      dy: `${Math.round(-50 + rnd() * 100)}px`,
      delay: `${-rnd() * 40}s`,
    }));
  }, [words]);
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
      {placed.map((p, i) => (
        <span
          key={i}
          className="dash-drift-word"
          style={{ left: p.left, top: p.top, fontSize: p.size, "--o": p.o, "--d": `${p.d}s`, "--dx": p.dx, "--dy": p.dy, "--delay": p.delay } as CSSProperties}
        >
          {p.word}
        </span>
      ))}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_40%,transparent_0%,var(--color-surface-dark)_75%)]" />
    </div>
  );
}
