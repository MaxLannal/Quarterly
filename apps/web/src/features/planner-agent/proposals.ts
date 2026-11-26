/**
 * Planner proposals (issue #18): each course or sequence the planner agent proposes, kept as
 * unsaved blocks on the grid until the student accepts or rejects it (decision D1: they stay
 * after the panel closes and after a reload).
 */
import type { ChangeOp, Citation, GroupKind, PlanState, PlannerProposalEvent, RuleRef } from "@/api/types";
import { applyOps, ChangeOpError } from "@/features/planner/changes";

export interface Proposal {
  /** The change set id of a saved plan, else `<runId>:<groupId>`. */
  id: string;
  changeSetId: string | null;
  groupId: string;
  title: string;
  kind: GroupKind;
  ops: ChangeOp[];
  why: string;
  citations: Citation[];
  rules: RuleRef[];
  status: "proposed" | "stale";
  runId: string;
}

export interface ProposedBlock {
  proposalId: string;
  course: string;
  action: "add" | "move-in" | "remove";
}

export function fromEvent(e: PlannerProposalEvent, runId: string): Proposal {
  return {
    id: e.change_set_id ?? `${runId}:${e.group_id}`,
    changeSetId: e.change_set_id ?? null,
    groupId: e.group_id,
    title: e.title,
    kind: e.kind,
    ops: e.ops,
    why: e.why,
    citations: e.citations,
    rules: e.rules,
    status: "proposed",
    runId,
  };
}

/** The unsaved blocks of the open proposals, keyed by quarter. */
export function proposedBlocks(plan: PlanState, proposals: readonly Proposal[]): Map<string, ProposedBlock[]> {
  const out = new Map<string, ProposedBlock[]>();
  const push = (term: string, block: ProposedBlock) => out.set(term, [...(out.get(term) ?? []), block]);
  for (const p of proposals) {
    if (p.status !== "proposed") continue;
    for (const op of p.ops) {
      if (!op.course) continue;
      if (op.op === "add") push(op.term, { proposalId: p.id, course: op.course, action: "add" });
      else if (op.op === "move") push(op.to_term, { proposalId: p.id, course: op.course, action: "move-in" });
      else if (op.op === "remove") {
        const term = op.term ?? (plan.items ?? []).find((i) => i.course === op.course)?.term;
        if (term) push(term, { proposalId: p.id, course: op.course, action: "remove" });
      }
    }
  }
  return out;
}

/** Whether the proposal's ops still apply to the plan (a course added twice does not fit). */
export function stillFits(plan: PlanState, p: Proposal): boolean {
  const have = new Set((plan.items ?? []).map((i) => i.course));
  if (p.ops.some((op) => op.op === "add" && op.course && have.has(op.course))) return false;
  try {
    applyOps(plan, p.ops);
    return true;
  } catch (e) {
    if (e instanceof ChangeOpError) return false;
    throw e;
  }
}

/** The ops plus a lock for each course they place: an accepted course is locked (issue #18). */
export function withLocks(_plan: PlanState, ops: readonly ChangeOp[]): ChangeOp[] {
  const locks: ChangeOp[] = [];
  for (const op of ops) {
    if (op.op === "add" && op.course) locks.push({ op: "lock", item_id: null, course: op.course, slot_ref: null, term: op.term });
    if (op.op === "move" && op.course) locks.push({ op: "lock", item_id: null, course: op.course, slot_ref: null, term: op.to_term });
  }
  return [...ops, ...locks];
}
