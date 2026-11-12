import { useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { isNotAvailable } from "@/api/client";
import { streamChat } from "@/api/sse";
import type { ChangeOp, ChangeSet, Citation, PlanState } from "@/api/types";
import { Button } from "@/components/ui/button";
import { NotAvailable, Notice } from "@/components/ui/misc";
import { opText } from "@/features/planner/context";
import { ReportBadge } from "@/features/planner/VerifierBadge";

type Entry =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string; citations: Citation[] }
  | { kind: "proposal"; changeSet: ChangeSet; state: "proposed" | "applied" | "dismissed" };

export function CitationChip({ c }: { c: Citation }) {
  const cls = "inline-flex min-h-8 items-center rounded-full border border-border bg-muted px-2 text-xs";
  if (c.kind === "course") {
    return (
      <Link to={`/courses/${encodeURIComponent(c.id)}`} className={`${cls} underline-offset-2 hover:underline`}>
        {c.label}
      </Link>
    );
  }
  if (c.kind === "program") {
    return (
      <Link to={`/programs/${encodeURIComponent(c.id)}`} className={`${cls} hover:underline`}>
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
    <article className="rounded-md border border-blue-700 bg-blue-50/50 p-2 text-sm" aria-label="Proposed change">
      <h4 className="font-semibold">Proposed change</h4>
      <ul className="my-1 list-disc pl-5">
        {changeSet.ops.map((op, i) => (
          <li key={i}>{opText(op)}</li>
        ))}
      </ul>
      {changeSet.preview_report && (
        <p className="flex items-center gap-2">
          After this change: <ReportBadge report={changeSet.preview_report} />
        </p>
      )}
      {state === "proposed" ? (
        <div className="mt-2 flex gap-2">
          <Button onClick={onApply}>Apply</Button>
          <Button variant="outline" onClick={onDismiss}>
            Dismiss
          </Button>
        </div>
      ) : (
        <p className="mt-1 text-xs text-muted-foreground">{state === "applied" ? "Applied." : "Dismissed."}</p>
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
      <ol className="space-y-2" aria-label="Advisor messages" aria-live="polite">
        {entries.length === 0 && <li className="text-sm text-muted-foreground">Ask a planning question, for example “Which elective is lighter?”</li>}
        {entries.map((entry, i) => (
          <li key={i}>
            {entry.kind === "user" ? (
              <div className="ml-6 rounded-md bg-muted p-2 text-sm">
                <span className="sr-only">You: </span>
                {entry.text}
              </div>
            ) : entry.kind === "assistant" ? (
              <div className="mr-6 rounded-md border border-border p-2 text-sm">
                <span className="sr-only">Advisor: </span>
                <p>{entry.text}</p>
                {entry.citations.length > 0 && (
                  <ul className="mt-1 flex flex-wrap gap-1" aria-label="Sources">
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
          <li role="status" className="text-sm text-muted-foreground">
            Thinking…
          </li>
        )}
      </ol>
      {error && (
        <Notice tone="red" role="alert">
          {error}
        </Notice>
      )}
      <form onSubmit={send} className="flex flex-col gap-2">
        <label htmlFor={inputId} className="text-sm font-medium">
          Ask the advisor
        </label>
        <textarea
          id={inputId}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          maxLength={4000}
          className="rounded-md border border-border bg-background p-2 text-sm"
        />
        <Button type="submit" disabled={busy || !text.trim()}>
          Send
        </Button>
      </form>
    </div>
  );
}
