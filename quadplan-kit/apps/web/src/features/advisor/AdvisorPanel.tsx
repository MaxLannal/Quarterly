import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, isNotAvailable, unwrap } from "@/api/client";
import { streamChat } from "@/api/sse";
import type { ChangeOp, ChangeSet, ChatTurn, Citation, PlanState } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { NotAvailable, Notice } from "@/components/ui/misc";
import { applyStoredChangeSet } from "@/features/generate/deterministic";
import { opText } from "@/features/planner/context";
import { termLabel } from "@/features/planner/terms";
import { ReportBadge } from "@/features/planner/VerifierBadge";

type CardState = "proposed" | "applied" | "dismissed";
type Entry =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string; citations: Citation[] }
  | { kind: "proposal"; changeSet: ChangeSet; state: CardState };

export function CitationChip({ c }: { c: Citation }) {
  // Citation chip: a 32px neutral pill drawn inside a transparent 6px border, so links keep a 44px
  // target (same technique as Button size "sm"). Tabular Inter: course codes never use the serif.
  const cls =
    "inline-flex min-h-11 items-center rounded-pill border-[6px] border-transparent bg-surface-strong bg-clip-padding px-3 text-caption tabular-nums text-ink";
  const link = `${cls} underline underline-offset-2 hover:bg-hairline focus-visible:outline-offset-[-4px]`;
  if (c.kind === "course") {
    return (
      <Link to={`/courses/${encodeURIComponent(c.id)}`} className={link}>
        {c.label}
      </Link>
    );
  }
  if (c.kind === "program") {
    return (
      <Link to={`/programs/${encodeURIComponent(c.id)}`} className={link}>
        {c.label}
      </Link>
    );
  }
  return (
    <span className={cls} title={`${c.kind}: ${c.id}`}>
      {c.label}
    </span>
  );
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

export function ProposalCard({
  changeSet,
  state,
  onApply,
  onDismiss,
}: {
  changeSet: ChangeSet;
  state: CardState;
  onApply: () => void;
  onDismiss: () => void;
}) {
  const phrase = confirmationPhrase(changeSet.ops);
  return (
    <article className="rounded-xl border border-hairline-strong bg-surface-card p-4 text-body-sm text-ink" aria-label="Proposed change">
      <h4 className="text-caption-uppercase uppercase text-muted">Proposed change</h4>
      <ul className="my-2 list-disc pl-5 marker:text-gray-dark">
        {changeSet.ops.map((op, i) => (
          <li key={i}>{opText(op)}</li>
        ))}
      </ul>
      {changeSet.preview_report && (
        <p className="flex flex-wrap items-center gap-2 text-body">
          After this change: <ReportBadge report={changeSet.preview_report} />
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

export function AdvisorPanel({ plan, planId = null, onApply }: AdvisorPanelProps) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const runId = useRef<string | null>(null);
  const inputId = useId();

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

  return (
    <div className="flex flex-col gap-3">
      {unavailable && <NotAvailable feature="The advisor">Planning questions will work once the chat service is built.</NotAvailable>}
      <ol className="space-y-3" aria-label="Advisor messages" aria-live="polite">
        {entries.length === 0 && (
          <li className="rounded-lg bg-canvas-soft p-4 text-body-sm text-muted">Ask a planning question, for example “Which elective is lighter?”</li>
        )}
        {entries.map((entry, i) => (
          <li key={i}>
            {entry.kind === "user" ? (
              <div className="ml-8 rounded-lg rounded-br-xs bg-surface-strong px-4 py-3 text-body-sm text-ink">
                <span className="sr-only">You: </span>
                {entry.text}
              </div>
            ) : entry.kind === "assistant" ? (
              <div className="mr-8 rounded-lg rounded-bl-xs border border-hairline bg-surface-card px-4 py-3 text-body-sm text-body">
                <span className="sr-only">Advisor: </span>
                <p>{entry.text}</p>
                {entry.citations.length > 0 && (
                  <ul className="mt-1 flex flex-wrap" aria-label="Sources">
                    {entry.citations.map((c) => (
                      <li key={`${c.kind}-${c.id}`}>
                        <CitationChip c={c} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <ProposalCard
                changeSet={entry.changeSet}
                state={entry.state}
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
            )}
          </li>
        ))}
        {busy && (
          <li role="status" className="text-body-sm text-muted">
            Thinking…
          </li>
        )}
      </ol>
      {error && (
        <Notice tone="error" role="alert">
          {error}
        </Notice>
      )}
      <form onSubmit={send} className="flex flex-col gap-2">
        <label htmlFor={inputId} className="text-caption font-medium text-ink">
          Ask the advisor
        </label>
        <Textarea id={inputId} value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={4000} className="text-body-sm" />
        <Button type="submit" className="self-end" disabled={busy || !text.trim()}>
          Send
        </Button>
      </form>
    </div>
  );
}
