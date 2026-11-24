import { Fragment, useEffect, useId, useMemo, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useFocusTrap } from "@/components/ui/dialog";
import { CheckIcon, CloseIcon, SendIcon } from "@/components/ui/icons";
import { AnswerControl } from "@/features/profile/AnswerControls";
import { hasAnswer, questionById, type Question, type QuestionSet } from "@/features/profile/questions";
import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { patched, type Profile, type ProfilePatch, type TurnEvent } from "./api";
import { courseHref, discussedTopics, multiReply, seeded, SKIP, type Proposal } from "./logic";
import { GuideMark } from "./parts";
import type { Guide } from "./useGuide";

/**
 * The dashboard agent, immersive (Issue #16): a full-screen ink room. It asks one General
 * Information question at a time in large Newsreader, with the question's options as buttons
 * (several chips sent together for a multi-choice question, 1 to 10 for a scale) and a box for a
 * typed answer. Each answer it understood waits as a card with Accept and Change; an accepted
 * answer is saved at once and the dashboard behind updates. Escape closes.
 */
export function GuideOverlay({ open, onClose, guide, profile, questions, catalogYear }: { open: boolean; onClose: () => void; guide: Guide; profile: Profile; questions: QuestionSet | undefined; catalogYear: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const [draft, setDraft] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  useFocusTrap(ref, open, onClose, composer);

  useEffect(() => {
    if (!open) return;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [open]);

  // Back to the composer once the guide answers; a new question starts with no chips picked.
  const answered = guide.status === "idle" && !!guide.current;
  const currentText = guide.current?.text;
  useEffect(() => {
    setPicked([]);
    if (open && answered) composer.current?.focus({ preventScroll: true });
  }, [open, answered, currentText]);

  if (!open) return null;
  const turn = guide.current;
  const thinking = guide.status === "thinking";
  const step2 = (questions?.questions ?? []).filter((q) => q.step === 2);
  const covered = new Set<string>([...step2.filter((q) => hasAnswer(profile, q)).map((q) => q.id), ...profile.interview.covered, ...discussedTopics(guide.turns)]);
  const progress = turn?.progress ?? (step2.length ? step2.filter((q) => covered.has(q.id)).length / step2.length : 0);
  const lastStudent = guide.pending ?? [...guide.turns].reverse().find((t) => t.role === "student")?.text ?? null;
  const question = questionById(questions, turn?.topic);
  const multi = question?.type === "multi";

  function send(text: string) {
    guide.reply(text);
    setDraft("");
    setPicked([]);
  }

  return createPortal(
    <div
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-[60] flex animate-fade-in flex-col overflow-y-auto overscroll-contain bg-surface-dark text-on-dark"
    >
      <DriftingWords words={[...profile.programs.map((p) => p.name), ...profile.research_areas]} />
      <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-on-dark/10 bg-surface-dark/85 px-4 py-2 backdrop-blur sm:px-8">
        <GuideMark size={18} className={cn("text-primary", thinking && "dash-thinking")} />
        <h2 id={titleId} className="font-display text-title-md text-on-dark">
          Your guide
        </h2>
        <ProgressRail questions={step2} current={turn?.topic ?? null} covered={covered} progress={progress} />
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
        <div className="h-full bg-primary transition-[width] duration-700" style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>

      <div className="relative mx-auto grid w-full max-w-[1200px] flex-1 gap-8 px-4 pb-16 pt-8 sm:px-8 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-12 lg:pt-14">
        <div className="flex min-w-0 flex-col gap-6">
          {lastStudent && (
            <p className="max-w-[46rem] text-body-sm text-on-dark-soft">
              <span className="text-caption-uppercase uppercase">You said</span> <span className="italic">“{lastStudent.length > 220 ? `${lastStudent.slice(0, 220)}…` : lastStudent}”</span>
            </p>
          )}

          {guide.proposals.length > 0 && (
            <ul className="flex flex-col gap-2" aria-label="Answers to accept">
              {guide.proposals.map((p) => (
                <ProposalCard key={p.id} proposal={p} guide={guide} profile={profile} questions={questions} catalogYear={catalogYear} />
              ))}
            </ul>
          )}

          <div className="min-h-[9rem]">
            {turn && !thinking ? (
              <>
                {turn.retry && <p className="mb-2 text-body-sm text-on-dark-soft">I could not match that to an answer. Pick one of the options, or put it another way.</p>}
                <Question key={turn.text} text={turn.text} />
                <p aria-live="polite" className="sr-only">
                  {turn.retry ? "I could not match that to an answer. " : ""}
                  {turn.text}
                </p>
                {question?.help && <p className="mt-3 max-w-[46rem] text-body-sm text-on-dark-soft">{question.help}</p>}
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
            <QuickReplies turn={turn} question={question} multi={multi} picked={picked} setPicked={setPicked} onSend={send} />
          )}

          {turn?.done && !thinking && (
            <div className="dash-rise flex flex-wrap items-center gap-3 rounded-xl border border-on-dark/15 bg-surface-dark-elevated p-4">
              <p className="min-w-0 flex-1 text-body-sm text-on-dark">Your guide has no more questions. Accepted answers are already on your dashboard.</p>
              <Link to="/plan" onClick={onClose} className="inline-flex min-h-11 items-center rounded-pill bg-primary px-5 text-button text-on-primary hover:bg-primary-hover">
                Open the planner
              </Link>
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
              placeholder={thinking ? "Your guide is thinking…" : "Or type your answer…"}
              className="min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-body-md text-on-dark outline-none placeholder:text-on-dark-soft disabled:opacity-60"
            />
            <button type="submit" disabled={thinking || !draft.trim()} aria-label="Send your answer" className="inline-flex size-11 shrink-0 items-center justify-center rounded-pill bg-primary text-on-primary hover:bg-primary-hover disabled:bg-on-dark/15 disabled:text-on-dark-soft">
              <SendIcon size={18} />
            </button>
          </form>
          <p className="text-caption text-on-dark-soft">
            {turn?.fallback ? "Your guide is running without the AI right now; it asks the same questions." : "Your guide is an AI and can be wrong."} Nothing is saved until you accept it. Enter sends, Shift+Enter starts a new line.
          </p>
        </div>

        <aside aria-label="Your answers" className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
          <AcceptedPanel guide={guide} />
        </aside>
      </div>
    </div>,
    document.body,
  );
}

/** The question's options as buttons: one press answers; for a multi-choice question the chips
 * are picked first and sent together. "Skip" is a normal reply. */
function QuickReplies({ turn, question, multi, picked, setPicked, onSend }: { turn: TurnEvent; question: Question | undefined; multi: boolean; picked: string[]; setPicked: (p: string[]) => void; onSend: (text: string) => void }) {
  const options = turn.quick_replies.filter((q) => q !== SKIP);
  const skip = turn.quick_replies.includes(SKIP);
  const scale = question?.type === "scale";
  const chip = "dash-rise min-h-11 rounded-pill border px-4 text-body-sm transition-colors";
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2" role="group" aria-label={multi ? "Choose all that apply, then send" : "Quick answers"}>
        {options.map((q, i) => {
          const on = picked.includes(q);
          return (
            <button
              key={q}
              type="button"
              aria-pressed={multi ? on : undefined}
              onClick={() => (multi ? setPicked(on ? picked.filter((p) => p !== q) : [...picked, q]) : onSend(q))}
              style={{ "--delay": `${200 + i * 40}ms` } as CSSProperties}
              className={cn(chip, scale && "w-11 px-0 tabular-nums", on ? "border-primary bg-primary text-on-primary" : "border-on-dark/25 text-on-dark hover:border-on-dark/60 hover:bg-on-dark/10")}
            >
              {multi && on && <CheckIcon size={14} className="mr-1 inline" />}
              {q}
            </button>
          );
        })}
        {multi && (
          <button type="button" disabled={picked.length === 0} onClick={() => onSend(multiReply(picked, options))} className="min-h-11 rounded-pill bg-primary px-5 text-button text-on-primary hover:bg-primary-hover disabled:bg-on-dark/15 disabled:text-on-dark-soft">
            Send {picked.length ? `(${picked.length})` : ""}
          </button>
        )}
        {skip && (
          <button type="button" onClick={() => onSend(SKIP)} className={cn(chip, "border-transparent text-on-dark-soft underline underline-offset-4 hover:bg-on-dark/10 hover:text-on-dark")}>
            {SKIP}
          </button>
        )}
      </div>
      {scale && question?.ends && (
        <p aria-hidden="true" className="flex max-w-[34rem] justify-between text-caption text-on-dark-soft">
          <span>
            {question.min ?? 1} = {question.ends.min}
          </span>
          <span>
            {question.max ?? 10} = {question.ends.max}
          </span>
        </p>
      )}
    </div>
  );
}

/** One answer the guide understood: Accept saves it; Change opens the question's own control,
 * and saving that saves the changed answer instead. */
function ProposalCard({ proposal, guide, profile, questions, catalogYear }: { proposal: Proposal; guide: Guide; profile: Profile; questions: QuestionSet | undefined; catalogYear: string }) {
  const [changing, setChanging] = useState(false);
  const question = questionById(questions, proposal.id);
  const proposedProfile = useMemo(() => patched(profile, proposal.patch), [profile, proposal.patch]);
  const [edit, setEdit] = useState<unknown>(() => (question ? (proposedProfile as unknown as Record<string, unknown>)[question.field] : null));
  return (
    <li className="dash-rise rounded-xl bg-surface-card p-3 text-ink shadow-overlay sm:p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-primary">{proposal.label}</p>
          <p className="text-body-md text-ink">{proposal.value}</p>
        </div>
        {!changing && (
          <div className="flex gap-1">
            <button type="button" onClick={() => guide.accept(proposal)} aria-label={`Accept ${proposal.label}: ${proposal.value}`} className="inline-flex min-h-11 items-center gap-1.5 rounded-pill bg-primary px-4 text-button text-on-primary hover:bg-primary-hover">
              <CheckIcon size={16} /> Accept
            </button>
            {question && (
              <button type="button" onClick={() => setChanging(true)} aria-label={`Change ${proposal.label}`} className="min-h-11 rounded-pill px-4 text-button text-ink shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-surface-strong">
                Change
              </button>
            )}
          </div>
        )}
      </div>
      {changing && question && (
        <div className="mt-3 flex flex-col gap-3 border-t border-hairline pt-3">
          <AnswerControl question={question} set={questions} value={edit} onChange={setEdit} classYear={profile.class_year} catalogYear={catalogYear} programNames={new Map(profile.programs.map((p) => [p.id, p.name]))} layout={question.value === "program" ? "form" : "panel"} />
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => guide.accept(proposal, { [question.field]: edit } as ProfilePatch)} className="min-h-11 rounded-pill bg-primary px-4 text-button text-on-primary hover:bg-primary-hover">
              Save this answer
            </button>
            <button type="button" onClick={() => setChanging(false)} className="min-h-11 rounded-pill px-4 text-button text-ink hover:bg-surface-strong">
              Cancel
            </button>
            <button type="button" onClick={() => guide.dismiss(proposal)} className="min-h-11 rounded-pill px-4 text-button text-muted underline underline-offset-4 hover:bg-surface-strong">
              Leave it unanswered
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

function Question({ text }: { text: string }) {
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <p aria-hidden="true" className="max-w-[46rem] font-serif text-[28px] font-light leading-[1.18] tracking-[-0.3px] text-on-dark text-balance sm:text-[40px] sm:leading-[1.12]">
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
      <p className="flex items-center gap-3 font-serif text-[26px] font-light italic text-on-dark-soft sm:text-[32px]">
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

/** The step-2 questions as a rail: done ones checked, the current one filled. */
function ProgressRail({ questions, current, covered, progress }: { questions: Question[]; current: string | null; covered: Set<string>; progress: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, progress)) * 100);
  return (
    <div className="ml-2 hidden min-w-0 flex-1 items-center gap-3 md:flex" aria-label={`Conversation ${pct}% done`} role="group">
      <ol className="flex min-w-0 flex-wrap items-center gap-1">
        {questions.map((q) => {
          const isCurrent = q.id === current;
          const done = covered.has(q.id) && !isCurrent;
          return (
            <li key={q.id} className="flex items-center gap-1" aria-current={isCurrent ? "step" : undefined}>
              <span className={cn("inline-flex min-h-7 items-center rounded-pill px-2.5 text-[12px] font-medium", isCurrent ? "bg-primary text-on-primary" : done ? "text-on-dark" : "text-on-dark-soft")}>
                {done && <CheckIcon size={11} className="mr-1 text-on-dark-soft" />}
                {q.label}
              </span>
            </li>
          );
        })}
      </ol>
      <span className="text-caption tabular-nums text-on-dark-soft">{pct}%</span>
    </div>
  );
}

function AcceptedPanel({ guide }: { guide: Guide }) {
  const { accepted } = guide;
  return (
    <div className="flex flex-col gap-3 rounded-xxl border border-on-dark/15 bg-surface-dark-elevated/70 p-4">
      <h3 className="font-display text-title-md text-on-dark">Saved to your profile</h3>
      {accepted.length === 0 ? (
        <p className="text-body-sm text-on-dark-soft">Answer with a button or in your own words. Each answer waits for your Accept before it is saved.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {accepted.map((p) => (
            <li key={p.id} className="flex items-start gap-2 rounded-xl bg-surface-dark px-3 py-2 text-body-sm">
              <CheckIcon size={14} className="mt-1 shrink-0 text-success" />
              <span className="min-w-0">
                <span className="block text-[11px] font-semibold uppercase tracking-wider text-on-dark-soft">{p.label}</span>
                <span className="text-on-dark">{p.value}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Words from the student's record, drifting slowly behind the conversation (still under reduced motion). */
function DriftingWords({ words }: { words: string[] }) {
  const key = words.join("|");
  const placed = useMemo(() => {
    const list = key ? key.split("|") : ["curiosity", "the Core", "a question", "Hyde Park", "the quarter"];
    const rnd = seeded(list.length * 7919 + 13);
    const still = prefersReducedMotion();
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
  }, [key]);
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
