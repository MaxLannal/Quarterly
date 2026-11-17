import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import type { PlanState, VariantEvent } from "@/api/types";
import type { GenerateFormValue } from "./GenerateDialog";

type S = components["schemas"];

/**
 * Which generator the Generate popup uses. `agent` (the default since prompt 07) = the agent
 * harness over SSE (`POST /agents/generate`), which works without an LLM through its fallbacks;
 * `deterministic` = the solver alone (`POST /plans/generate?mode=deterministic`, prompt 06).
 * Set at build time with VITE_GENERATOR_MODE.
 */
export const GENERATOR_MODE: "deterministic" | "agent" =
  import.meta.env.VITE_GENERATOR_MODE === "deterministic" ? "deterministic" : "agent";

/** The quarter a date falls in (Summer counts toward the next Autumn: nothing is planned in it). */
export function currentTerm(date: Date = new Date()): string {
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  if (month <= 3) return `${year}-WI`;
  if (month <= 6) return `${year}-SP`;
  return `${year}-AU`;
}

export interface DeterministicResult {
  variants: VariantEvent[];
  infeasible: S["Infeasibility"] | null;
}

/**
 * Applies a stored change set on the server: "Apply", "Apply selected quarters", or the
 * advisor's typed confirmation (`confirmationText`, which the server parses again).
 */
export async function applyStoredChangeSet(
  planId: string,
  cs: { id?: string | null; base_plan_hash: string },
  terms: string[] | null,
  confirmationText: string | null = null,
): Promise<void> {
  if (!cs.id) return;
  unwrap(
    await api.POST("/plans/{plan_id}/changesets/{changeset_id}/apply", {
      params: { path: { plan_id: planId, changeset_id: cs.id } },
      body: { base_plan_hash: cs.base_plan_hash, terms, confirmation_text: confirmationText },
    }),
  );
}

export function toOptions(v: GenerateFormValue, today: string = currentTerm()): S["GenerateOptions"] {
  return {
    scope: v.scope,
    selected_terms: v.scope === "selected" ? v.selectedTerms : [],
    today_term: v.scope === "remaining" ? today : null,
    load: v.load,
    per_term_load: v.perTermLoad,
    max_courses_per_term: v.maxCourses,
    allow_overload: v.allowOverload,
    goals: v.goals,
    interests: v.interests,
    variants: v.variants,
    allow_rarely_offered: [],
    preferences: null,
    time_limit_s: 3,
  };
}

/**
 * A saved plan (`planId`, unchanged since it was saved) is generated for on the server and each
 * variant is stored as a change set; a plan that lives only in the browser uses the stateless
 * endpoint and nothing is saved.
 */
export async function generateDeterministic(
  plan: PlanState,
  v: GenerateFormValue,
  signal?: AbortSignal,
  planId: string | null = null,
): Promise<DeterministicResult> {
  const out = unwrap(
    planId
      ? await api.POST("/plans/{plan_id}/generate", {
          params: { path: { plan_id: planId }, query: { mode: "deterministic" } },
          body: toOptions(v),
          signal,
        })
      : await api.POST("/plans/generate", {
          body: { plan, options: toOptions(v) },
          params: { query: { mode: "deterministic" } },
          signal,
        }),
  );
  return {
    variants: out.variants.map((x) => ({
      type: "variant",
      label: x.label,
      change_set: x.change_set,
      report: x.report,
      metrics: x.metrics ?? {},
      rationale: x.rationale ?? {},
      citations: [],
    })),
    infeasible: out.infeasible ?? null,
  };
}
