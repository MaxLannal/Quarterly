/**
 * The edit history of a plan (issue #18): each applied edit with the ops that undo it. A local
 * plan keeps it in the plan; a saved plan keeps it in localStorage under `historyKey`.
 */
import type { ChangeOp, PlanItem, PlanState } from "@/api/types";

export interface HistoryEntry {
  id: string;
  /** Day-level date only. */
  day: string;
  label: string;
  ops: ChangeOp[];
  inverse: ChangeOp[];
}

export const HISTORY_LIMIT = 50;

export function historyKey(planKey: string): string {
  return `quarterly.history.v1:${planKey}`;
}

const keyOf = (i: PlanItem) => i.course ?? `slot:${i.slot_ref ?? ""}`;

function target(i: PlanItem): { item_id: null; course: string | null; slot_ref: string | null } {
  return { item_id: null, course: i.course ?? null, slot_ref: i.course ? null : (i.slot_ref ?? null) };
}

/** The ops that turn `after` back into `before` (matched by course, or slot). */
export function inverseOps(before: PlanState, after: PlanState): ChangeOp[] {
  const was = new Map((before.items ?? []).map((i) => [keyOf(i), i]));
  const now = new Map((after.items ?? []).map((i) => [keyOf(i), i]));
  const unlock: ChangeOp[] = [];
  const undo: ChangeOp[] = [];
  const relock: ChangeOp[] = [];
  for (const [key, item] of now) {
    const old = was.get(key);
    if (item.locked && (!old || !old.locked || old.term !== item.term)) {
      unlock.push({ op: "unlock", ...target(item), term: item.term });
    }
    if (!old) {
      undo.push({ op: "remove", ...target(item), term: item.term });
    } else if (old.term !== item.term) {
      undo.push({ op: "move", ...target(item), from_term: item.term, to_term: old.term });
      if (old.locked) relock.push({ op: "lock", ...target(old), term: old.term });
    } else if (old.locked && !item.locked) {
      relock.push({ op: "lock", ...target(old), term: old.term });
    }
  }
  for (const [key, old] of was) {
    if (now.has(key)) continue;
    undo.push({
      op: "add",
      course: old.course ?? null,
      slot_ref: old.course ? null : (old.slot_ref ?? null),
      term: old.term,
      status: old.status ?? "planned",
      units: old.units ?? null,
      grading: old.grading ?? "letter",
      locked: old.locked ?? false,
    });
  }
  return [...unlock, ...undo, ...relock];
}

export function newHistoryId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `h-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
