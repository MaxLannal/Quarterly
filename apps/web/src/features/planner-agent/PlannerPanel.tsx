/**
 * The planner agent's panel beside the plan (issue #18): the conversation (the student's
 * working information and questions, the agent's answers, questions, plans and proposals), the
 * walkthrough of a new plan, and a composer. It says that an AI writes the answers.
 */
import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode, type RefObject } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { CloseIcon, SparkIcon } from "@/components/ui/icons";
import { NotAvailable, Notice } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { CitationChip } from "./CitationChip";
import { PlannerProposalCard } from "./PlannerProposalCard";
import type { ThreadEntry } from "./thread";
import type { PlannerRun } from "./usePlannerRun";

function AiRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 pr-2">
      <span aria-hidden="true" className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-strong text-ink">
        <SparkIcon size={16} />
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

/** A question of the planner: its options as buttons, and an "Other" box (issue #18 step 9). */
function QuestionCard({ entry, onAnswer, busy }: { entry: Extract<ThreadEntry, { kind: "question" }>; onAnswer: (option: string | null, text: string | null) => void; busy: boolean }) {
  const [other, setOther] = useState("");
  const otherId = useId();
  const q = entry.event;
  const done = entry.answered !== undefined;
  return (
    <div className="rounded-xl border border-hairline-strong bg-surface-card p-4 text-body-sm" data-testid="planner-question">
      <p className="font-medium text-ink">{q.text}</p>
      {done ? (
        <p className="mt-2 text-caption text-muted">You answered: {entry.answered}</p>
      ) : (
        <>
          {q.options.length > 0 && (
            <ul className="mt-3 flex flex-col gap-2" aria-label="Options">
              {q.options.map((o) => (
                <li key={o}>
                  <Button variant="outline" className="h-auto min-h-11 w-full justify-start whitespace-normal py-2 text-left" disabled={busy} onClick={() => onAnswer(o, null)}>
                    {o}
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {q.allow_other !== false && (
            <form
              className="mt-3 flex items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (other.trim()) onAnswer(null, other.trim());
              }}
            >
              <div className="min-w-0 flex-1">
                <label htmlFor={otherId} className="mb-1 block text-caption text-muted">
                  {q.options.length ? "Other" : "Your answer"}
                </label>
                <input
                  id={otherId}
                  value={other}
                  onChange={(e) => setOther(e.target.value)}
                  className="min-h-11 w-full rounded-md border border-hairline-strong bg-surface-card px-3 text-body-sm text-ink focus-visible:outline-2 focus-visible:outline-primary"
                />
              </div>
              <Button type="submit" disabled={busy || !other.trim()}>
                Send
              </Button>
            </form>
          )}
        </>
      )}
    </div>
  );
}

interface PlannerPanelProps {
  run: PlannerRun;
  onClose: () => void;
  /** The proposal a block on the grid selected. */
  selected: string | null;
  /** Shown above the conversation while a walkthrough runs. */
  walkthrough?: ReactNode;
  onReplay?: () => void;
  composerRef: RefObject<HTMLTextAreaElement>;
  headingId: string;
  className?: string;
}

export function PlannerPanel({ run, onClose, selected, walkthrough, onReplay, composerRef, headingId, className }: PlannerPanelProps) {
  const [text, setText] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputId = useId();

  // Escape hides the panel (issue #18 step 20), also when focus left it (an accepted card goes
  // away); a dialog on top (clear chat, programs, the drawer on a phone) handles its own Escape.
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || confirmClear) return;
      const target = e.target instanceof Element ? e.target : null;
      const dialog = target?.closest('[role="dialog"]');
      if (dialog && !rootRef.current?.closest('[role="dialog"]')?.isSameNode(dialog)) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [confirmClear, onClose]);
  const open = run.proposals.filter((p) => p.status === "proposed");

  useEffect(() => {
    const el = scrollRef.current;
    if (el && !walkthrough) el.scrollTop = el.scrollHeight;
  }, [run.entries.length, run.running, walkthrough]);

  useEffect(() => {
    if (!selected) return;
    document.querySelector(`[data-testid="planner-proposal"][data-proposal="${CSS.escape(selected)}"]`)?.scrollIntoView?.({ block: "nearest" });
  }, [selected]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || run.running) return;
    run.send(text);
    setText("");
  }

  function onComposerKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <div ref={rootRef} className={cn("flex min-h-0 flex-col bg-canvas", className)}>
      <header className="border-b border-hairline px-4 py-3">
        <div className="flex items-center gap-2">
          {/* FEEDBACK 2026-11-16: "Ask Quarterly", without the grey "Generative AI" badge; the
              line below still says that an AI writes the answers. */}
          <h2 id={headingId} className="min-w-0 flex-1 font-display text-title-lg">
            Ask Quarterly
          </h2>
          <Button variant="ghost" onClick={() => setConfirmClear(true)} disabled={run.entries.length === 0}>
            Clear chat
          </Button>
          <Button variant="ghost" size="icon" aria-label="Close planner" onClick={onClose} className="-mr-2">
            <CloseIcon />
          </Button>
        </div>
        <p className="mt-1 text-caption text-muted">Answers are written by an AI and can be wrong. Not official advising.</p>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4" data-testid="planner-scroll">
        {run.unavailable && (
          <div className="mb-4">
            <NotAvailable feature="The planner" />
          </div>
        )}
        {walkthrough}
        <ol className="flex flex-col gap-4" aria-label="Planner messages">
          {run.entries.length === 0 && !walkthrough && (
            <li className="mx-auto max-w-sm py-8 text-center text-body-sm text-muted">
              Press Generate plan for a first plan, or tell me what you want: “I hate this course”, “a lighter Autumn in year 2”, “why is this here?”
            </li>
          )}
          {run.entries.map((entry, i) => (
            <li key={i} className="animate-rise">
              <Entry entry={entry} run={run} selected={selected} onReplay={onReplay} />
            </li>
          ))}
          {run.running && (
            <li>
              <AiRow>
                <div className="flex h-10 items-center gap-1 rounded-xl rounded-tl-xs border border-hairline bg-surface-card px-4" data-testid="typing-indicator">
                  <span className="sr-only">The planner is working</span>
                  {[0, 150, 300].map((d) => (
                    <span key={d} aria-hidden="true" className="inline-block size-1.5 animate-typing rounded-pill bg-gray-dark" style={{ animationDelay: `${d}ms` }} />
                  ))}
                </div>
              </AiRow>
            </li>
          )}
        </ol>
      </div>

      {open.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 border-t border-hairline px-4 py-2">
          <span className="text-caption text-muted">{open.length} open proposals</span>
          <Button size="sm" onClick={() => void run.acceptAll()}>
            Accept all
          </Button>
          <Button size="sm" variant="outline" onClick={() => void run.rejectAll()}>
            Reject all
          </Button>
        </div>
      )}

      <form onSubmit={submit} className="flex items-end gap-2 border-t border-hairline px-4 py-3">
        <div className="min-w-0 flex-1">
          <label htmlFor={inputId} className="sr-only">
            Ask or tell the planner
          </label>
          <textarea
            id={inputId}
            ref={composerRef}
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onComposerKey}
            placeholder="Ask or tell the planner…"
            className="block max-h-40 min-h-11 w-full resize-y rounded-md border border-hairline-strong bg-surface-card px-3 py-2 text-body-sm text-ink focus-visible:outline-2 focus-visible:outline-primary"
          />
        </div>
        <Button type="submit" disabled={run.running || !text.trim()}>
          Send
        </Button>
      </form>

      <div className="sr-only" aria-live="polite" data-testid="planner-live">
        {run.announcement}
      </div>

      <Dialog open={confirmClear} onClose={() => setConfirmClear(false)} title="Clear the chat?" description="The conversation goes. Open proposals stay on your plan.">
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setConfirmClear(false)}>
            Keep it
          </Button>
          <Button
            onClick={() => {
              setConfirmClear(false);
              void run.clear();
            }}
          >
            Clear chat
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

function Entry({ entry, run, selected, onReplay }: { entry: ThreadEntry; run: PlannerRun; selected: string | null; onReplay?: () => void }) {
  switch (entry.kind) {
    case "user":
      return (
        <div className="flex justify-end">
          <div className="max-w-[85%] whitespace-pre-wrap rounded-xl rounded-tr-xs bg-primary-wash px-4 py-2.5 text-body-sm text-ink" data-testid="chat-bubble-user">
            <span className="sr-only">You: </span>
            {entry.text}
          </div>
        </div>
      );
    case "assistant":
      return (
        <AiRow>
          <div className="w-fit max-w-full rounded-xl rounded-tl-xs border border-hairline bg-surface-card px-4 py-2.5 text-body-sm text-body" data-testid="chat-bubble-ai">
            <span className="sr-only">Planner (AI): </span>
            <p className="whitespace-pre-wrap">{entry.text}</p>
            {entry.citations.length > 0 && (
              <ul className="-mx-1.5 mt-1 flex flex-wrap" aria-label="Sources">
                {entry.citations.map((c) => (
                  <li key={`${c.kind}-${c.id}`}>
                    <CitationChip c={c} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </AiRow>
      );
    case "steps":
      return (
        <AiRow>
          <ul className="space-y-1 text-caption text-muted" aria-label="Planner steps">
            {entry.steps.map((s) => (
              <li key={s.name} className="flex items-center gap-2">
                <span aria-hidden="true">{s.status === "done" ? "✓" : s.status === "failed" ? "!" : "…"}</span>
                {s.name}
                <span className="sr-only"> ({s.status})</span>
              </li>
            ))}
          </ul>
        </AiRow>
      );
    case "question":
      return (
        <AiRow>
          <QuestionCard entry={entry} busy={run.running} onAnswer={(option, text) => run.answer(entry.event.question_id, option, text)} />
        </AiRow>
      );
    case "plan": {
      const errors = (entry.event.issues ?? []).filter((i) => i.level === "error").length;
      return (
        <AiRow>
          <div className="rounded-xl border border-hairline bg-surface-card px-4 py-3 text-body-sm" data-testid="planner-plan">
            <p className="font-medium text-ink">{entry.event.verdict === "valid" ? "Your plan passes the plan check." : `Your plan is not valid yet (${errors} ${errors === 1 ? "problem" : "problems"}).`}</p>
            {entry.event.summary && <p className="mt-1 text-body">{entry.event.summary}</p>}
            <p className="mt-1 text-caption text-muted">Each part below is a proposal: accept or reject it. Nothing changes until you do.</p>
            {onReplay && (
              <Button variant="outline" size="sm" className="mt-2" onClick={onReplay}>
                Walk me through it
              </Button>
            )}
          </div>
        </AiRow>
      );
    }
    case "proposal": {
      const p = run.proposals.find((x) => x.id === entry.proposalId);
      if (!p) return <p className="pl-11 text-caption text-muted">A proposal you accepted or rejected.</p>;
      return (
        <AiRow>
          <PlannerProposalCard proposal={p} selected={selected === p.id} onAccept={() => void run.accept(p.id)} onReject={() => void run.reject(p.id)} onAskAgain={() => run.askAgain(p.id)} />
        </AiRow>
      );
    }
    case "error":
      return (
        <Notice tone="error">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>{entry.text}</span>
            {entry.reason === "expired" && (
              <Button size="sm" variant="outline" onClick={run.generate}>
                Start again
              </Button>
            )}
          </div>
        </Notice>
      );
  }
}
