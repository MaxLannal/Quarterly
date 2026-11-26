import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/misc";
import { opText } from "@/features/planner/context";
import { cn } from "@/lib/utils";
import { CitationChip } from "./CitationChip";
import type { Proposal } from "./proposals";

const KIND_LABEL: Record<Proposal["kind"], string> = {
  major: "Major",
  core: "Core",
  elective: "Elective",
  minor: "Minor",
  replace: "Removal",
  other: "Other",
};

/**
 * One planner proposal (issue #18): the group's courses with their quarters, why it suits this
 * student, its sources and the guideline rules it follows, with Accept and Reject. A stale one
 * (the plan changed so it no longer fits) offers Ask again instead.
 */
export function PlannerProposalCard({
  proposal,
  selected = false,
  onAccept,
  onReject,
  onAskAgain,
  footer,
  label,
}: {
  proposal: Proposal;
  /** The card's accessible name (default "Proposal: <title>"). */
  label?: string;
  selected?: boolean;
  onAccept: () => void;
  onReject: () => void;
  onAskAgain: () => void;
  /** Extra controls (the walkthrough's Back / Next). */
  footer?: ReactNode;
}) {
  const rules = new Map(proposal.rules.map((r) => [r.id, r.text]));
  return (
    <article
      aria-label={label ?? `Proposal: ${proposal.title}`}
      data-testid="planner-proposal"
      data-proposal={proposal.id}
      className={cn(
        "rounded-xl border border-hairline-strong bg-surface-card p-4 text-body-sm text-ink",
        selected && "ring-2 ring-primary ring-offset-2 ring-offset-canvas",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="font-semibold text-ink">{proposal.title}</h4>
        <Badge casing="normal" className="px-2 py-0">
          {KIND_LABEL[proposal.kind]}
        </Badge>
      </div>
      <ul className="my-2 list-disc pl-5 marker:text-gray-dark" aria-label="Changes">
        {proposal.ops.map((op, i) => (
          <li key={i}>{opText(op)}</li>
        ))}
      </ul>
      {proposal.why && (
        <p className="text-body">
          <span className="font-medium">Why this for you: </span>
          {proposal.why}
        </p>
      )}
      {(proposal.citations.length > 0 || proposal.rules.length > 0) && (
        <ul className="-mx-1.5 mt-1 flex flex-wrap" aria-label="Sources and rules">
          {proposal.citations.map((c) => (
            <li key={`${c.kind}-${c.id}`}>
              <CitationChip c={c} rules={rules} />
            </li>
          ))}
          {proposal.rules.map((r) => (
            <li key={`rule-${r.id}`}>
              <CitationChip c={{ kind: "guideline", id: r.id, label: `Guideline ${r.id}` }} rules={rules} />
            </li>
          ))}
        </ul>
      )}
      {proposal.status === "stale" ? (
        <div className="mt-3 space-y-2">
          <p className="text-body text-warning-icon">This proposal no longer fits your plan.</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={onAskAgain}>
              Ask again
            </Button>
            <Button variant="ghost" onClick={onReject}>
              Remove
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={onAccept}>Accept</Button>
          <Button variant="outline" onClick={onReject}>
            Reject
          </Button>
        </div>
      )}
      {footer}
    </article>
  );
}
