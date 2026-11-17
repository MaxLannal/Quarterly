/**
 * Plan editing as change ops. Every grid interaction (drag, "Move to...", lock, mark
 * completed, remove, add) becomes a list of ops applied with `applyOps`, the same operations the
 * server accepts in `PATCH /plans/{id}/items`.
 */
import type { ChangeOp, Credit, Goal, PlanItem, PlanProgram, PlanState } from "@/api/types";
import { applyOps, ChangeOpError } from "./changes";
import { MAX_PLAN_YEARS, catalogStartYear, classYearLabel, graduationTerm, isBefore, planYearCount, termAt, yearIndex } from "./terms";

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
  | { type: "credits"; credits: Credit[] }
  | { type: "graduation"; term: string }
  | { type: "addYear" }
  | { type: "removeYear" }
  | { type: "replace"; plan: PlanState; name?: string }
  | { type: "dismissError" };

/** Plan years shown in the grid: up to the graduation quarter's year (FEEDBACK F3). */
export function planYears(plan: PlanState): number {
  return planYearCount(plan.entry_term, graduationTerm(plan));
}

/** Items in plan year `year` (by academic year, whatever the quarter). */
function itemsInYear(plan: PlanState, year: number): PlanItem[] {
  return (plan.items ?? []).filter((i) => {
    try {
      return yearIndex(i.term, plan.entry_term) === year;
    } catch {
      return false;
    }
  });
}

const TOO_LONG = `A plan can be at most ${MAX_PLAN_YEARS} years long.`;

/** "Add a year": graduate in the Spring of the year after the current last year. */
export function addYear(plan: PlanState): { ok: true; plan: PlanState } | { ok: false; error: string } {
  const years = planYears(plan);
  if (years >= MAX_PLAN_YEARS) return { ok: false, error: TOO_LONG };
  return { ok: true, plan: { ...plan, graduation_term: termAt(plan.entry_term, years + 1, "SP") } };
}

/** "Remove last year": refused while that year has courses, or when it is the only year. */
export function removeYear(plan: PlanState): { ok: true; plan: PlanState } | { ok: false; error: string } {
  const years = planYears(plan);
  const label = classYearLabel(years, plan.entry_year_level ?? 1).toLowerCase();
  const last = termAt(plan.entry_term, years - 1, "SP");
  if (years <= 1 || isBefore(last, plan.entry_term)) return { ok: false, error: "A plan needs at least one year." };
  if (itemsInYear(plan, years).length > 0) return { ok: false, error: `Your ${label} has courses. Move or remove them first.` };
  return { ok: true, plan: { ...plan, graduation_term: last } };
}

export function initEditor(plan: PlanState, name: string): EditorState {
  return { plan: ensureIds(plan), name, revision: 0, error: null };
}

function withOps(state: EditorState, ops: ChangeOp[]): EditorState {
  if (ops.length === 0) return state;
  try {
    const plan = applyOps(state.plan, ops, { newId: newItemId });
    return { ...state, plan, revision: state.revision + 1, error: null };
  } catch (e) {
    if (e instanceof ChangeOpError) return { ...state, error: e.message };
    throw e;
  }
}

function withPlan(state: EditorState, plan: PlanState): EditorState {
  return { ...state, plan, revision: state.revision + 1, error: null };
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
    case "credits":
      return withPlan(state, { ...state.plan, credits: action.credits });
    case "graduation":
      if (action.term.endsWith("-SU")) return { ...state, error: "You cannot graduate in a Summer quarter." };
      if (isBefore(action.term, state.plan.entry_term)) return { ...state, error: "Your last quarter cannot be before your first." };
      if (yearIndex(action.term, state.plan.entry_term) > MAX_PLAN_YEARS) return { ...state, error: TOO_LONG };
      return withPlan(state, { ...state.plan, graduation_term: action.term });
    case "addYear": {
      const r = addYear(state.plan);
      return r.ok ? withPlan(state, r.plan) : { ...state, error: r.error };
    }
    case "removeYear": {
      const r = removeYear(state.plan);
      return r.ok ? withPlan(state, r.plan) : { ...state, error: r.error };
    }
    case "replace":
      return { ...state, plan: ensureIds(action.plan), name: action.name ?? state.name, revision: state.revision + 1, error: null };
    case "dismissError":
      return { ...state, error: null };
  }
}
