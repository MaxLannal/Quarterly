import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode, type RefObject } from "react";
import { Link } from "react-router-dom";
import { api, isNotAvailable, unwrap } from "@/api/client";
import { streamChat } from "@/api/sse";
import type { ChangeOp, ChangeSet, ChatTurn, Citation, PlanState, Report } from "@/api/types";
import { Button } from "@/components/ui/button";
import { CloseIcon, SparkIcon } from "@/components/ui/icons";
import { NotAvailable, Notice } from "@/components/ui/misc";
import { TopSheet } from "@/components/ui/sheet";
import { useSession } from "@/features/auth/session";
import { useForumPageById, usePost } from "@/features/forum/api";
import { pagePath, threadPath } from "@/features/forum/format";
import { applyStoredChangeSet } from "@/features/generate/deterministic";
import { opText } from "@/features/planner/context";
import { termLabel } from "@/features/planner/terms";
import { ReportBadge } from "@/features/planner/VerifierBadge";
import "./advisor.css";

type CardState = "proposed" | "applied" | "dismissed";
type Entry =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string; citations: Citation[] }
  | { kind: "proposal"; changeSet: ChangeSet; state: CardState };

// Citation chip: a 32px neutral pill drawn inside a transparent 6px border, so links keep a 44px
// target (same technique as Button size "sm"). Tabular Inter: course codes never use the serif.
const chipClass =
  "inline-flex min-h-11 items-center rounded-pill border-[6px] border-transparent bg-surface-strong bg-clip-padding px-3 text-caption tabular-nums text-ink";
// D11 AD-3: a linked chip is told apart by its maroon text, not an underline inside a pill.
const chipLinkClass = `${chipClass} text-primary hover:bg-hairline hover:text-primary-hover focus-visible:outline-offset-[-4px]`;

/** "workload 13 h/wk · n=34" reads as "Workload 13 h/wk (34 ratings)" (D11 AD-3). */
export function chipLabel(label: string): string {
  const t = label.replace(/\s*·\s*n=(\d+)/, (_, n: string) => ` (${n} rating${n === "1" ? "" : "s"})`);
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function ChipLink({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} className={chipLinkClass}>
      {chipLabel(label)}
    </Link>
  );
}

/**
 * A forum citation (`post:POST_ID` or `summary:PAGE_ID`). The id alone cannot build the URL
 * (`/courses/:code/i/:instructor/t/:id`), so the chip asks the API for the post (which names its
 * page) and the page (which names the course and instructor). Forum reads need a login, so a
 * logged-out student, a removed post or a failed request keeps a plain chip: same pill, no
 * underline, nothing to click.
 */
function ForumCitationChip({ c }: { c: Citation }) {
  const session = useSession();
  const loggedIn = session.status === "authenticated";
  const isPost = c.kind === "post";
  const post = usePost(isPost ? Number(c.id) : Number.NaN, loggedIn && isPost);
  const pageId = isPost ? post.data?.page_id : Number(c.id);
  const page = useForumPageById(pageId ?? Number.NaN, loggedIn && pageId != null);
  if (page.data) {
    const { course_code: code, instructor } = page.data;
    return <ChipLink to={isPost ? threadPath(code, instructor.slug, Number(c.id)) : pagePath(code, instructor.slug)} label={c.label} />;
  }
  return <span className={chipClass}>{chipLabel(c.label)}</span>;
}

export function CitationChip({ c }: { c: Citation }) {
  if (c.kind === "course") return <ChipLink to={`/courses/${encodeURIComponent(c.id)}`} label={c.label} />;
  if (c.kind === "program") return <ChipLink to={`/programs/${encodeURIComponent(c.id)}`} label={c.label} />;
  if (c.kind === "attribute") {
    // `CODE:key` (for example "CMSC 14300:workload_hours"): the attribute is shown on the course page.
    const code = c.id.slice(0, c.id.lastIndexOf(":"));
    if (code) return <ChipLink to={`/courses/${encodeURIComponent(code)}`} label={c.label} />;
  }
  if (c.kind === "post" || c.kind === "summary") return <ForumCitationChip c={c} />;
  return <span className={chipClass}>{chipLabel(c.label)}</span>;
}

/**
 * The sentence a student can type to confirm a proposal, when every operation names a course and
 * its quarters (the server's parser reads exactly this form). Null otherwise: use Apply.
 */
export function confirmationPhrase(ops: ChangeOp[]): string | null {
  const parts: string[] = [];
  for (const op of ops) {
    if (op.op === "add" && op.course && !op.locked && (op.status ?? "planned") === "planned") parts.push(`add ${op.course} to ${termLabel(op.term)}`);
    else if (op.op === "move" && op.course && !op.item_id) parts.push(`move ${op.course}${op.from_term ? ` from ${termLabel(op.from_term)}` : ""} to ${termLabel(op.to_term)}`);
    else if (op.op === "remove" && op.course && !op.item_id) parts.push(`remove ${op.course}${op.term ? ` from ${termLabel(op.term)}` : ""}`);
    else return null;
  }
  return parts.length ? `I agree to ${parts.join(" and ")}` : null;
}

const errorsIn = (r: Report) => (r.issues ?? []).filter((i) => i.level === "error").length;

/** "(no change)", "(1 fewer)" or "(2 more)" errors after the change than now (AD-1, D11). */
function errorDelta(now: Report, after: Report): string {
  const d = errorsIn(after) - errorsIn(now);
  if (d === 0) return now.status === after.status ? "no change" : "same number of errors";
  return d < 0 ? `${-d} fewer error${d === -1 ? "" : "s"}` : `${d} more error${d === 1 ? "" : "s"}`;
}

export function ProposalCard({
  changeSet,
  state,
  current = null,
  onApply,
  onDismiss,
}: {
  changeSet: ChangeSet;
  state: CardState;
  /** The plan check now, so the preview has something to compare with (AD-1, D11). */
  current?: Report | null;
  onApply: () => void;
  onDismiss: () => void;
}) {
  const phrase = confirmationPhrase(changeSet.ops);
  return (
    <article className="border border-hairline rounded-[22px] bg-canvas-soft p-5 text-body-sm text-ink " aria-label="Proposed change">
      <h4 className="text-[12px] font-semibold flex items-center gap-2 text-muted">
        <span aria-hidden="true" className="inline-block size-1.5 rounded-pill bg-primary " />
        Proposed change
      </h4>
      <ul className="my-2 list-disc pl-5 marker:text-gray-dark">
        {changeSet.ops.map((op, i) => (
          <li key={i}>{opText(op)}</li>
        ))}
      </ul>
      {changeSet.preview_report && (
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body">
          {current && (
            <>
              Now: <ReportBadge report={current} />
              <span aria-hidden="true" className="text-muted">→</span>
            </>
          )}
          After this change: <ReportBadge report={changeSet.preview_report} />
          {current && <span className="text-caption text-muted">({errorDelta(current, changeSet.preview_report)})</span>}
        </p>
      )}
      {state === "proposed" ? (
        <>
          <div className="mt-3 flex gap-2">
            <Button onClick={onApply}>Apply</Button>
            <Button variant="outline" onClick={onDismiss}>
              Dismiss
            </Button>
          </div>
          <p className="mt-2 text-caption text-muted">
            {phrase ? <>Or type “{phrase}” or “apply it”.</> : <>Or type “apply it”.</>}
          </p>
        </>
      ) : (
        <p className="mt-2 text-caption text-muted">{state === "applied" ? "Applied." : "Dismissed."}</p>
      )}
    </article>
  );
}

interface AdvisorPanelProps {
  plan: PlanState;
  /** The saved plan's id when the plan is unchanged since it was saved; null otherwise. */
  planId?: string | null;
  /** Applies the ops to the plan in the browser; returns true when they applied cleanly. */
  onApply: (ops: ChangeOp[]) => boolean;
  /** Ref to the message box (the advisor sheet focuses it on open). */
  composerRef?: RefObject<HTMLTextAreaElement>;
  /** The plan check now, shown beside each proposal's preview (AD-1, D11). */
  currentReport?: Report | null;
}

const MAX_HISTORY = 12;

function turnsOf(entries: Entry[]): ChatTurn[] {
  const turns: ChatTurn[] = [];
  for (const e of entries) {
    if (e.kind === "user") turns.push({ role: "user", text: e.text.slice(0, 4000) });
    else if (e.kind === "assistant") turns.push({ role: "assistant", text: e.text.slice(0, 4000) });
  }
  return turns.slice(-MAX_HISTORY);
}

function sameOps(a: ChangeSet, b: ChangeSet): boolean {
  return a.id && b.id ? a.id === b.id : JSON.stringify(a.ops) === JSON.stringify(b.ops) && a.base_plan_hash === b.base_plan_hash;
}

export function AdvisorPanel({ plan, planId = null, onApply, composerRef, currentReport = null }: AdvisorPanelProps) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const runId = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const ownInputRef = useRef<HTMLTextAreaElement>(null);
  const inputRef = composerRef ?? ownInputRef;
  const inputId = useId();

  // Keep the newest message in view.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [entries.length, busy]);

  // A saved plan's conversation lives on the server (30 days).
  useEffect(() => {
    if (!planId) return;
    let live = true;
    void api
      .GET("/agents/chat/history", { params: { query: { plan_id: planId } } })
      .then((res) => {
        if (!live) return;
        const history = unwrap(res);
        runId.current = history.run_id ?? null;
        setEntries(
          (history.entries ?? []).flatMap((e): Entry[] => {
            if (e.role === "proposal") return e.change_set ? [{ kind: "proposal", changeSet: e.change_set, state: e.change_set.status === "applied" ? "applied" : e.change_set.status === "proposed" ? "proposed" : "dismissed" }] : [];
            if (e.role === "user") return [{ kind: "user", text: e.text ?? "" }];
            return [{ kind: "assistant", text: e.text ?? "", citations: e.citations ?? [] }];
          }),
        );
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [planId]);

  function setCard(cs: ChangeSet, state: CardState) {
    setEntries((xs) => xs.map((x) => (x.kind === "proposal" && sameOps(x.changeSet, cs) ? { ...x, state } : x)));
  }

  /** Applies a change set: on the server first for a saved plan, then in the browser. */
  async function applyChangeSet(cs: ChangeSet, confirmationText: string | null): Promise<boolean> {
    if (planId && cs.id) {
      try {
        await applyStoredChangeSet(planId, cs, null, confirmationText);
      } catch {
        setError("Your plan changed since this proposal, or the confirmation did not match. Ask again.");
        return false;
      }
    }
    if (!onApply(cs.ops)) {
      setError("This change no longer fits your plan.");
      return false;
    }
    setCard(cs, "applied");
    return true;
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    const latest = [...entries].reverse().find((x): x is Extract<Entry, { kind: "proposal" }> => x.kind === "proposal" && x.state === "proposed");
    const history = planId ? [] : turnsOf(entries);
    setText("");
    setError(null);
    setEntries((xs) => [...xs, { kind: "user", text: message }]);
    setBusy(true);
    try {
      const body = { message, plan, plan_id: planId, run_id: runId.current, history, latest_proposal: planId ? null : (latest?.changeSet ?? null) };
      for await (const ev of streamChat(body)) {
        if (ev.type === "message") setEntries((xs) => [...xs, { kind: "assistant", text: ev.text, citations: ev.citations ?? [] }]);
        else if (ev.type === "proposal") setEntries((xs) => [...xs, { kind: "proposal", changeSet: ev.change_set, state: "proposed" }]);
        else if (ev.type === "confirm") {
          const ok = await applyChangeSet(ev.change_set, ev.confirmation_text);
          if (ok) setEntries((xs) => [...xs, { kind: "assistant", text: `Applied: ${ev.change_set.ops.map(opText).join("; ")}.`, citations: [] }]);
        } else if (ev.type === "done") runId.current = ev.run_id;
        else if (ev.type === "error") setError(ev.message);
      }
    } catch (err) {
      if (isNotAvailable(err)) setUnavailable(true);
      else setError("The advisor could not answer. Try again.");
    } finally {
      setBusy(false);
    }
  }


  function onComposerKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter starts a new line (the usual chat convention).
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6" data-testid="advisor-scroll">
        {unavailable && (
          <div className="mb-4">
            <NotAvailable feature="The advisor" />
          </div>
        )}
        <ol className="flex flex-col gap-4" aria-label="Advisor messages" aria-live="polite">
          {entries.length === 0 && (
            <li className="mx-auto flex max-w-sm flex-col items-center gap-4 py-12 text-center text-body-sm text-muted">
              <span aria-hidden="true" className="advisor-orb size-14" />
              Ask a planning question, for example “Which elective is lighter?”
            </li>
          )}
          {entries.map((entry, i) => (
            <li key={i} className="animate-rise">
              {entry.kind === "user" ? (
                <div className="flex justify-end">
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-[22px] rounded-tr-md bg-surface-strong px-4 py-2.5 text-body-sm text-ink " data-testid="chat-bubble-user">
                    <span className="sr-only">You: </span>
                    {entry.text}
                  </div>
                </div>
              ) : entry.kind === "assistant" ? (
                <AiRow>
                  <div className="w-fit max-w-full rounded-[22px] rounded-tl-md bg-canvas-soft px-4 py-2.5 text-body-sm text-body " data-testid="chat-bubble-ai">
                    <span className="sr-only">Quarterly (AI): </span>
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
              ) : (
                <AiRow>
                  <ProposalCard
                    changeSet={entry.changeSet}
                    state={entry.state}
                    current={currentReport}
                    onApply={() => {
                      setError(null);
                      void applyChangeSet(entry.changeSet, null);
                    }}
                    onDismiss={() => {
                      setCard(entry.changeSet, "dismissed");
                      const id = entry.changeSet.id;
                      if (planId && id) {
                        void api.POST("/plans/{plan_id}/changesets/{changeset_id}/discard", { params: { path: { plan_id: planId, changeset_id: id } } }).catch(() => undefined);
                      }
                    }}
                  />
                </AiRow>
              )}
            </li>
          ))}
          {busy && (
            <li role="status" className="animate-fade-in">
              <AiRow>
                <div className="flex h-10 items-center gap-1 rounded-[22px] rounded-tl-md bg-canvas-soft px-4 " data-testid="typing-indicator">
                  <span className="sr-only">The AI is writing…</span>
                  {[0, 150, 300].map((d) => (
                    <span key={d} aria-hidden="true" className="inline-block size-1.5 animate-typing rounded-pill bg-primary " style={{ animationDelay: `${d}ms` }} />
                  ))}
                </div>
              </AiRow>
            </li>
          )}
        </ol>
      </div>
      {error && (
        <div className="px-4 pb-2 sm:px-6">
          <Notice tone="error" role="alert">
            {error}
          </Notice>
        </div>
      )}
      <form onSubmit={send} className="px-4 pb-4 pt-2 sm:px-6 sm:pb-5">
        <label htmlFor={inputId} className="sr-only">
          Ask the advisor
        </label>
        <div className="flex items-end gap-2 rounded-[26px] border border-border-input bg-canvas-soft py-1 pl-4 pr-1 transition-[border-color,box-shadow] duration-300 focus-within:border-primary ">
          <textarea
            ref={inputRef}
            id={inputId}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onComposerKey}
            rows={2}
            maxLength={4000}
            placeholder="Ask about your plan"
            className="min-h-11 flex-1 resize-none bg-transparent py-2 text-body-sm text-ink placeholder:text-muted focus-visible:outline-none"
          />
          <Button type="submit" disabled={busy || !text.trim()}>
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}

/** An AI turn: the AI avatar, then the bubble or card. */
function AiRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 pr-6 sm:pr-12">
      <span aria-hidden="true" className="advisor-orb mt-0.5 flex size-8 shrink-0 items-center justify-center text-ink">
        <SparkIcon size={15} />
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

/**
 * The advisor's own surface: a sheet that slides down from the top (a full page on a phone),
 * labelled as generative AI (FEEDBACK F4). The conversation stays when the sheet is closed.
 */
export function AdvisorSheet({ open, onClose, ...panel }: AdvisorPanelProps & { open: boolean; onClose: () => void }) {
  const titleId = useId();
  const descId = useId();
  const composer = useRef<HTMLTextAreaElement>(null);
  return (
    <TopSheet open={open} onClose={onClose} labelledBy={titleId} describedBy={descId} initialFocus={composer}>
      <header className="flex items-start gap-3 border-b border-hairline px-4 py-3 sm:px-6 sm:py-5">
        <span aria-hidden="true" className="advisor-orb mt-1 hidden size-11 shrink-0 items-center justify-center text-ink sm:flex">
          <SparkIcon size={19} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id={titleId} className="font-display text-display-sm leading-tight">
              Ask Quarterly
            </h2>
          </div>
          <p id={descId} className="mt-1 text-caption text-muted">
            Answers are written by an AI and can be wrong. Not official advising.
          </p>
        </div>
        <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose} className="-mr-2">
          <CloseIcon />
        </Button>
      </header>
      <AdvisorPanel {...panel} composerRef={composer} />
    </TopSheet>
  );
}
