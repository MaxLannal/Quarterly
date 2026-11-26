/**
 * The walkthrough of a new plan (issue #18): one proposal group at a time, in plan order
 * (major sequences, then the Core, minors, electives, the rest, and removals last; within a
 * kind, the earliest quarter first). The page lights the current group's blocks. Accepting or
 * rejecting the current group moves on by itself: it drops out of the list.
 */
import { useCallback, useMemo, useState } from "react";
import { termKey } from "@/features/planner/terms";
import type { Proposal } from "./proposals";

const KIND_ORDER: Record<Proposal["kind"], number> = { major: 0, core: 1, minor: 2, elective: 3, other: 4, replace: 5 };

function firstTerm(p: Proposal): number {
  const keys = p.ops.flatMap((op) => (op.op === "add" ? [op.term] : op.op === "move" ? [op.to_term] : op.op === "remove" && op.term ? [op.term] : [])).map(termKey);
  return keys.length ? Math.min(...keys) : Number.MAX_SAFE_INTEGER;
}

export function walkOrder(proposals: readonly Proposal[]): Proposal[] {
  return [...proposals].sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || firstTerm(a) - firstTerm(b));
}

export interface Walkthrough {
  /** 0-based; `total` when every group was shown; null when no walkthrough runs. */
  step: number | null;
  total: number;
  current: Proposal | null;
  start: (ids?: readonly string[]) => void;
  next: () => void;
  back: () => void;
  stop: () => void;
}

export function useWalkthrough(proposals: readonly Proposal[]): Walkthrough {
  const [ids, setIds] = useState<string[] | null>(null);
  const [step, setStep] = useState<number | null>(null);
  // The groups still open, in the walkthrough's order (accepted or rejected ones drop out).
  const order = useMemo(() => {
    if (!ids) return [];
    const chosen = new Set(ids);
    return walkOrder(proposals.filter((p) => p.status === "proposed" && chosen.has(p.id)));
  }, [ids, proposals]);
  const at = step === null ? null : Math.min(step, order.length);

  const start = useCallback(
    (only?: readonly string[]) => {
      const chosen = only ?? proposals.filter((p) => p.status === "proposed").map((p) => p.id);
      if (!chosen.length) return;
      setIds([...chosen]);
      setStep(0);
    },
    [proposals],
  );
  const next = useCallback(() => setStep((s) => (s === null ? s : Math.min(s + 1, order.length))), [order.length]);
  const back = useCallback(() => setStep((s) => (s === null ? s : Math.max(0, Math.min(s, order.length) - 1))), [order.length]);
  const stop = useCallback(() => {
    setStep(null);
    setIds(null);
  }, []);

  return { step: at, total: order.length, current: at === null ? null : (order[at] ?? null), start, next, back, stop };
}
