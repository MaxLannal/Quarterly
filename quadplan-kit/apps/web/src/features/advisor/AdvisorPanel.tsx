import { useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { isNotAvailable } from "@/api/client";
import { streamChat } from "@/api/sse";
import type { ChangeOp, ChangeSet, Citation, PlanState } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { NotAvailable, Notice } from "@/components/ui/misc";
import { opText } from "@/features/planner/context";
import { ReportBadge } from "@/features/planner/VerifierBadge";

type Entry =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string; citations: Citation[] }
  | { kind: "proposal"; changeSet: ChangeSet; state: "proposed" | "applied" | "dismissed" };

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

export function ProposalCard({
  changeSet,
  state,
  onApply,
  onDismiss,
}: {
  changeSet: ChangeSet;
  state: "proposed" | "applied" | "dismissed";
  onApply: () => void;
  onDismiss: () => void;
}) {
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
        <div className="mt-3 flex gap-2">
          <Button onClick={onApply}>Apply</Button>
          <Button variant="outline" onClick={onDismiss}>
            Dismiss
          </Button>
        </div>
      ) : (
        <p className="mt-2 text-caption text-muted">{state === "applied" ? "Applied." : "Dismissed."}</p>
      )}
    </article>
  );
}

interface AdvisorPanelProps {
  plan: PlanState;
  onApply: (ops: ChangeOp[]) => boolean;
}

export function AdvisorPanel({ plan, onApply }: AdvisorPanelProps) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const runId = useRef<string | null>(null);
  const inputId = useId();

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    setText("");
    setError(null);
    setEntries((xs) => [...xs, { kind: "user", text: message }]);
    setBusy(true);
    try {
      for await (const ev of streamChat({ message, plan, plan_id: null, run_id: runId.current })) {
        if (ev.type === "message") setEntries((xs) => [...xs, { kind: "assistant", text: ev.text, citations: ev.citations }]);
        else if (ev.type === "proposal") setEntries((xs) => [...xs, { kind: "proposal", changeSet: ev.change_set, state: "proposed" }]);
        else if (ev.type === "done") runId.current = ev.run_id;
        else if (ev.type === "error") setError(ev.message);
      }
    } catch (err) {
      if (isNotAvailable(err)) setUnavailable(true);
      else setError("The advisor could not answer. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function setProposal(i: number, state: "applied" | "dismissed") {
    setEntries((xs) => xs.map((x, n) => (n === i && x.kind === "proposal" ? { ...x, state } : x)));
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
                  if (onApply(entry.changeSet.ops)) setProposal(i, "applied");
                }}
                onDismiss={() => setProposal(i, "dismissed")}
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
