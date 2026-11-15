/**
 * Logged-out plans live in localStorage (SPEC decision 6: "planner (local only)"). Every access
 * goes through `lib/storage`, which wraps localStorage in try/catch, so a blocked or full
 * storage never breaks the planner: the plan simply is not remembered.
 */
import type { PlanCreate, PlanState } from "@/api/types";
import { readJson, writeJson } from "@/lib/storage";
import { termAt } from "./terms";

export const STORAGE_KEY = "quarterly.plans.v1";

export interface LocalPlan {
  localId: string;
  name: string;
  isPrimary: boolean;
  state: PlanState;
  /** Day-level date only (no exact timestamps). */
  updatedDay: string;
  /**
   * Legacy: plan years shown in the old grid (4, or 5 with "Add Year 5"). No longer written; the
   * plan's `graduation_term` replaced it. `loadPlans` turns `years: 5` into a Spring-of-year-5
   * graduation quarter (FEEDBACK F3).
   */
  years?: number;
  /** Account ids this plan was already imported into (import on login). */
  importedFor?: string[];
  /** Server plan id once saved to an account. */
  remoteId?: string;
}

export interface LocalPlansDoc {
  version: 1;
  activeId: string | null;
  plans: LocalPlan[];
}

const EMPTY: LocalPlansDoc = { version: 1, activeId: null, plans: [] };

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function isDoc(value: unknown): value is LocalPlansDoc {
  return (
    !!value &&
    typeof value === "object" &&
    (value as LocalPlansDoc).version === 1 &&
    Array.isArray((value as LocalPlansDoc).plans)
  );
}

/**
 * Plans saved before the graduation quarter existed kept a `years` count instead. Four years was
 * the old grid's minimum, so only `years: 5` says something: graduate in the Spring of year 5.
 */
export function migrateLegacyYears(plan: LocalPlan): LocalPlan {
  const { years, ...rest } = plan;
  if (years === undefined) return plan;
  if (years !== 5 || rest.state.graduation_term) return rest;
  try {
    return { ...rest, state: { ...rest.state, graduation_term: termAt(rest.state.entry_term, 5, "SP") } };
  } catch {
    return rest;
  }
}

export function loadPlans(): LocalPlansDoc {
  const doc = readJson<unknown>(STORAGE_KEY);
  return isDoc(doc) ? { ...doc, plans: doc.plans.map(migrateLegacyYears) } : { ...EMPTY, plans: [] };
}

export function savePlans(doc: LocalPlansDoc): boolean {
  return writeJson(STORAGE_KEY, doc);
}

export function activePlan(doc: LocalPlansDoc = loadPlans()): LocalPlan | null {
  return doc.plans.find((p) => p.localId === doc.activeId) ?? doc.plans[0] ?? null;
}

export function newLocalId(): string {
  return `plan-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Insert or replace a plan and make it active. Returns whether it was stored. The import
 * bookkeeping already stored for this plan (`importedFor`, `remoteId`) is kept when the caller
 * does not set it: the planner autosaves from the plan it opened with, which predates an import
 * that ran while it was open, and dropping the ids would import or save the plan a second time.
 */
export function upsertPlan(plan: LocalPlan, makeActive = true): boolean {
  const doc = loadPlans();
  const idx = doc.plans.findIndex((p) => p.localId === plan.localId);
  const prev = idx >= 0 ? doc.plans[idx] : undefined;
  const importedFor = [...new Set([...(prev?.importedFor ?? []), ...(plan.importedFor ?? [])])];
  const stored = migrateLegacyYears({
    ...plan,
    ...(importedFor.length ? { importedFor } : {}),
    ...((plan.remoteId ?? prev?.remoteId) ? { remoteId: plan.remoteId ?? prev?.remoteId } : {}),
    updatedDay: today(),
  });
  if (idx >= 0) doc.plans[idx] = stored;
  else doc.plans.push(stored);
  if (stored.isPrimary) {
    doc.plans = doc.plans.map((p) => (p.localId === stored.localId ? p : { ...p, isPrimary: false }));
  }
  if (makeActive || !doc.activeId) doc.activeId = stored.localId;
  return savePlans(doc);
}

export function deletePlan(localId: string): boolean {
  const doc = loadPlans();
  doc.plans = doc.plans.filter((p) => p.localId !== localId);
  if (doc.activeId === localId) doc.activeId = doc.plans[0]?.localId ?? null;
  return savePlans(doc);
}

export function setActive(localId: string): boolean {
  const doc = loadPlans();
  if (!doc.plans.some((p) => p.localId === localId)) return false;
  doc.activeId = localId;
  return savePlans(doc);
}

/** Local plans not yet imported into this account. */
export function plansToImport(accountId: string, doc: LocalPlansDoc = loadPlans()): LocalPlan[] {
  return doc.plans.filter((p) => !(p.importedFor ?? []).includes(accountId));
}

export function toPlanCreate(plan: LocalPlan): PlanCreate {
  return { name: plan.name, is_primary: plan.isPrimary, state: plan.state };
}

/** The server plan id stored for a local plan (set by a save or by import on login). */
export function storedRemoteId(localId: string): string | undefined {
  return loadPlans().plans.find((p) => p.localId === localId)?.remoteId;
}

/**
 * Record a successful import: `imported` maps each local plan id to the account plan it became,
 * so a later Save updates that plan instead of creating a second one. The local copy is kept so
 * nothing is lost.
 */
export function markImported(accountId: string, imported: Record<string, string | undefined>): boolean {
  const doc = loadPlans();
  doc.plans = doc.plans.map((p) => {
    if (!(p.localId in imported)) return p;
    const remoteId = imported[p.localId] ?? p.remoteId;
    return { ...p, ...(remoteId ? { remoteId } : {}), importedFor: [...new Set([...(p.importedFor ?? []), accountId])] };
  });
  return savePlans(doc);
}
