/**
 * Logged-out plans live in localStorage (SPEC decision 6: "planner (local only)"). Every access
 * goes through `lib/storage`, which wraps localStorage in try/catch, so a blocked or full
 * storage never breaks the planner: the plan simply is not remembered.
 */
import type { PlanCreate, PlanState } from "@/api/types";
import { readJson, writeJson } from "@/lib/storage";

export const STORAGE_KEY = "quarterly.plans.v1";

export interface LocalPlan {
  localId: string;
  name: string;
  isPrimary: boolean;
  state: PlanState;
  /** Day-level date only (no exact timestamps). */
  updatedDay: string;
  /** Plan years shown in the grid (4 or 5). */
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

export function loadPlans(): LocalPlansDoc {
  const doc = readJson<unknown>(STORAGE_KEY);
  return isDoc(doc) ? doc : { ...EMPTY, plans: [] };
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

/** Insert or replace a plan and make it active. Returns whether it was stored. */
export function upsertPlan(plan: LocalPlan, makeActive = true): boolean {
  const doc = loadPlans();
  const idx = doc.plans.findIndex((p) => p.localId === plan.localId);
  const stored = { ...plan, updatedDay: today() };
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

/** Record a successful import. The local copy is kept so nothing is lost. */
export function markImported(accountId: string, localIds: string[]): boolean {
  const doc = loadPlans();
  doc.plans = doc.plans.map((p) =>
    localIds.includes(p.localId) ? { ...p, importedFor: [...new Set([...(p.importedFor ?? []), accountId])] } : p,
  );
  return savePlans(doc);
}
