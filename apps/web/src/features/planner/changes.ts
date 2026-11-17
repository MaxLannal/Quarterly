/**
 * Applying change-set operations to a plan, ported from
 * `packages/planner_core/planner_core/changes.py`. Pure: returns a new PlanState.
 *
 * Semantics (must match the server): ops apply in order; an existing item is targeted by
 * `item_id`, `course` or `slot_ref` plus an optional term (`from_term` for moves); a missing
 * or ambiguous target throws; locked items cannot be moved or removed (unlock first).
 */
import type { ChangeOp, PlanItem, PlanState } from "@/api/types";

export class ChangeOpError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChangeOpError";
  }
}

interface Target {
  item_id?: string | null;
  course?: string | null;
  slot_ref?: string | null;
}

function find(items: PlanItem[], target: Target, term: string | null | undefined): number {
  const hits: number[] = [];
  items.forEach((item, i) => {
    if (
      (target.item_id == null || item.id === target.item_id) &&
      (target.course == null || item.course === target.course) &&
      (target.slot_ref == null || item.slot_ref === target.slot_ref) &&
      (term == null || item.term === term)
    ) {
      hits.push(i);
    }
  });
  const label = target.item_id || target.course || target.slot_ref;
  if (hits.length === 0) {
    throw new ChangeOpError(`no plan item matches ${label}${term ? ` in ${term}` : ""}`);
  }
  if (hits.length > 1) throw new ChangeOpError(`${label} matches ${hits.length} items; give the term`);
  return hits[0] as number;
}

export interface ApplyOptions {
  /** Gives new items an id (the server leaves it null; the client needs one to target cards). */
  newId?: () => string;
}

/** Apply `ops` in order. Locked items cannot be moved or removed (unlock first). */
export function applyOps(plan: PlanState, ops: readonly ChangeOp[], options: ApplyOptions = {}): PlanState {
  const items: PlanItem[] = (plan.items ?? []).map((item) => ({ ...item }));
  for (const op of ops) {
    if (op.op === "add") {
      const item: PlanItem = {
        course: op.course ?? null,
        slot_ref: op.slot_ref ?? null,
        term: op.term,
        status: op.status,
        units: op.units ?? null,
        grading: op.grading,
        locked: op.locked,
      };
      if (options.newId) item.id = options.newId();
      items.push(item);
      continue;
    }
    const term = op.op === "move" ? op.from_term : op.term;
    const idx = find(items, op, term);
    const item = items[idx] as PlanItem;
    if (op.op === "lock" || op.op === "unlock") {
      items[idx] = { ...item, locked: op.op === "lock" };
    } else if (item.locked) {
      throw new ChangeOpError(`${item.course || item.slot_ref} in ${item.term} is locked`);
    } else if (op.op === "move") {
      items[idx] = { ...item, term: op.to_term };
    } else {
      items.splice(idx, 1);
    }
  }
  return { ...plan, items };
}

/** Ops that a change set applies to the given terms only ("Apply selected quarters"). */
export function opsForTerms(ops: readonly ChangeOp[], terms: readonly string[]): ChangeOp[] {
  const set = new Set(terms);
  return ops.filter((op) => {
    if (op.op === "add") return set.has(op.term);
    if (op.op === "move") return set.has(op.to_term) || (op.from_term != null && set.has(op.from_term));
    return op.term == null || set.has(op.term);
  });
}

/** Every term a change set touches, for the per-quarter apply picker. */
export function termsTouched(ops: readonly ChangeOp[]): string[] {
  const out = new Set<string>();
  for (const op of ops) {
    if (op.op === "add") out.add(op.term);
    else if (op.op === "move") {
      out.add(op.to_term);
      if (op.from_term) out.add(op.from_term);
    } else if (op.term) out.add(op.term);
  }
  return [...out];
}
