/**
 * The walkthrough of a new plan (issue #18; Max, 2026-11-27): the main sequences one at a time,
 * in plan order (major, then the Core, then minors; within a kind, the earliest quarter first).
 * A main sequence is a major, Core or minor group of two or more courses; single courses and
 * electives share one last step, so the tour stays short. The page lights the current step's
 * blocks. Nothing is accepted per step; a group kept or dropped elsewhere leaves the tour.
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

/** One step of the tour: a main sequence, or the rest of the plan together. */
export interface Step {
  id: string;
  title: string;
  members: Proposal[];
}

const MAIN_KINDS: ReadonlySet<Proposal["kind"]> = new Set(["major", "core", "minor"]);

function isMainSequence(p: Proposal): boolean {
  return MAIN_KINDS.has(p.kind) && p.ops.filter((op) => op.op === "add" || op.op === "move").length >= 2;
}

/** The tour's steps: each main sequence, then one step for everything else. */
export function walkSteps(order: readonly Proposal[]): Step[] {
  const steps: Step[] = order.filter(isMainSequence).map((p) => ({ id: p.id, title: p.title, members: [p] }));
  const rest = order.filter((p) => !isMainSequence(p));
  const only = rest[0];
  if (rest.length === 1 && only) steps.push({ id: only.id, title: only.title, members: [only] });
  else if (rest.length > 1) steps.push({ id: "rest", title: "Electives and the other courses", members: rest });
  return steps;
}

export interface Walkthrough {
  /** 0-based; `total` when every group was shown; null when no walkthrough runs. */
  step: number | null;
  total: number;
  current: Step | null;
  /** Every group of the tour, in order ("Keep this plan" applies them all). */
  groups: Proposal[];
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
  const steps = useMemo(() => walkSteps(order), [order]);
  const at = step === null ? null : Math.min(step, steps.length);

  const start = useCallback(
    (only?: readonly string[]) => {
      const chosen = only ?? proposals.filter((p) => p.status === "proposed").map((p) => p.id);
      if (!chosen.length) return;
      setIds([...chosen]);
      setStep(0);
    },
    [proposals],
  );
  const next = useCallback(() => setStep((s) => (s === null ? s : Math.min(s + 1, steps.length))), [steps.length]);
  const back = useCallback(() => setStep((s) => (s === null ? s : Math.max(0, Math.min(s, steps.length) - 1))), [steps.length]);
  const stop = useCallback(() => {
    setStep(null);
    setIds(null);
  }, []);

  return { step: at, total: steps.length, current: at === null ? null : (steps[at] ?? null), groups: order, start, next, back, stop };
}
