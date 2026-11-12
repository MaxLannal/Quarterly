/**
 * Plan editing as change ops. Every grid interaction (drag, "Move to...", lock, mark
 * completed, remove, add) becomes a list of ops applied with `applyOps`, the same operations the
 * server accepts in `PATCH /plans/{id}/items`.
 */
import type { ChangeOp, Goal, PlanItem, PlanProgram, PlanState } from "@/api/types";
import { applyOps, ChangeOpError } from "./changes";
import { catalogStartYear, yearIndex } from "./terms";

let counter = 0;
export function newItemId(): string {
  counter += 1;
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().slice(0, 8)
      : Math.random().toString(36).slice(2, 10);
  return `local-${rand}-${counter}`;
}

/** Items need an id so cards can target them; server items already have one. */
export function ensureIds(plan: PlanState): PlanState {
  const items = plan.items ?? [];
  if (items.every((i) => i.id)) return plan;
  return { ...plan, items: items.map((i) => (i.id ? i : { ...i, id: newItemId() })) };
}

export function emptyPlan(catalogYear: string, entryTerm?: string): PlanState {
  return {
    catalog_year: catalogYear,
    entry_term: entryTerm ?? `${catalogStartYear(catalogYear)}-AU`,
    entry_year_level: 1,
    items: [],
    credits: [],
    programs: [],
    goals: [],
    placements: [],
    overload_reasons: {},
  };
}

export function itemLabel(item: PlanItem): string {
  return item.course ?? item.slot_ref ?? "item";
}

export type EditResult = { ok: true; ops: ChangeOp[] } | { ok: false; error: string };

const ok = (ops: ChangeOp[]): EditResult => ({ ok: true, ops });
const fail = (error: string): EditResult => ({ ok: false, error });

/** Dropping (or "Move to...") an existing card onto a term. */
export function moveItemOps(item: PlanItem, toTerm: string): EditResult {
  if (item.term === toTerm) return ok([]);
  if (item.locked) return fail(`${itemLabel(item)} is locked. Unlock it before moving it.`);
  return ok([{ op: "move", item_id: item.id ?? null, from_term: item.term, to_term: toTerm }]);
}

/** Dropping a course from the requirement rail or search onto a term. */
export function addCourseOps(course: string, term: string): EditResult {
  return ok([
    { op: "add", course, slot_ref: null, term, status: "planned", grading: "letter", locked: false, units: null },
  ]);
}

/** Filling a dashed requirement slot with a course: remove the slot, add the course. */
export function fillSlotOps(slot: PlanItem, course: string): EditResult {
  if (slot.locked) return fail(`${itemLabel(slot)} is locked.`);
  return ok([
    { op: "remove", item_id: slot.id ?? null, term: slot.term },
    { op: "add", course, slot_ref: null, term: slot.term, status: "planned", grading: "letter", locked: false, units: null },
  ]);
}

export function toggleLockOps(item: PlanItem): EditResult {
  return ok([{ op: item.locked ? "unlock" : "lock", item_id: item.id ?? null, term: item.term }]);
}

export function removeItemOps(item: PlanItem): EditResult {
  if (item.locked) return fail(`${itemLabel(item)} is locked. Unlock it before removing it.`);
  return ok([{ op: "remove", item_id: item.id ?? null, term: item.term }]);
}

/**
 * Marking completed (or back to planned) is not its own op: it is remove + add with the new
 * status, keeping the lock. A locked item is unlocked first so the remove is allowed.
 */
export function setCompletedOps(item: PlanItem, completed: boolean): EditResult {
  const ops: ChangeOp[] = [];
  if (item.locked) ops.push({ op: "unlock", item_id: item.id ?? null, term: item.term });
  ops.push({ op: "remove", item_id: item.id ?? null, term: item.term });
  ops.push({
    op: "add",
    course: item.course ?? null,
    slot_ref: item.slot_ref ?? null,
    term: item.term,
    status: completed ? "completed" : "planned",
    grading: item.grading,
    locked: item.locked,
    units: item.units ?? null,
  });
  return ok(ops);
}

// ------------------------------------------------------------------------------------------
// Editor reducer
// ------------------------------------------------------------------------------------------

export interface EditorState {
  plan: PlanState;
  name: string;
  /** Plan years shown (4, or 5 with the optional Year 5). */
  years: number;
  /** Increments on every plan change; used to tell a generated variant is stale. */
  revision: number;
  error: string | null;
}

export type EditorAction =
  | { type: "ops"; ops: ChangeOp[] }
  | { type: "edit"; result: EditResult }
  | { type: "rename"; name: string }
  | { type: "programs"; programs: PlanProgram[] }
  | { type: "goals"; goals: Goal[] }
  | { type: "years"; years: number }
  | { type: "replace"; plan: PlanState; name?: string }
  | { type: "dismissError" };

/** Years needed to show every item (at least 4, at most 5 in the grid). */
export function yearsNeeded(plan: PlanState): number {
  let max = 4;
  for (const item of plan.items ?? []) {
    try {
      max = Math.max(max, yearIndex(item.term, plan.entry_term));
    } catch {
      // malformed term: shown in the "other terms" list instead
    }
  }
  return Math.min(max, 5);
}

export function initEditor(plan: PlanState, name: string, years?: number): EditorState {
  const withIds = ensureIds(plan);
  return { plan: withIds, name, years: Math.max(years ?? 4, yearsNeeded(withIds)), revision: 0, error: null };
}

function withOps(state: EditorState, ops: ChangeOp[]): EditorState {
  if (ops.length === 0) return state;
  try {
    const plan = applyOps(state.plan, ops, { newId: newItemId });
    return { ...state, plan, revision: state.revision + 1, error: null, years: Math.max(state.years, yearsNeeded(plan)) };
  } catch (e) {
    if (e instanceof ChangeOpError) return { ...state, error: e.message };
    throw e;
  }
}

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "ops":
      return withOps(state, action.ops);
    case "edit":
      return action.result.ok ? withOps(state, action.result.ops) : { ...state, error: action.result.error };
    case "rename":
      return { ...state, name: action.name };
    case "programs":
      return { ...state, plan: { ...state.plan, programs: action.programs }, revision: state.revision + 1 };
    case "goals":
      return { ...state, plan: { ...state.plan, goals: action.goals }, revision: state.revision + 1 };
    case "years":
      return { ...state, years: Math.max(4, Math.min(5, Math.max(action.years, yearsNeeded(state.plan)))) };
    case "replace": {
      const plan = ensureIds(action.plan);
      return {
        ...state,
        plan,
        name: action.name ?? state.name,
        revision: state.revision + 1,
        years: Math.max(state.years, yearsNeeded(plan)),
        error: null,
      };
    }
    case "dismissError":
      return { ...state, error: null };
  }
}
