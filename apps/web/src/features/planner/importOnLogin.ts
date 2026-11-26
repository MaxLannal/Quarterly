import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import { useSession } from "@/lib/session";
import { loadPlans, markImported, plansToImport, toPlanCreate, type LocalPlan } from "./localPlans";

export type ImportStatus = "idle" | "importing" | "imported" | "unavailable" | "failed";

/**
 * POST the local plans to /plans/import once a session exists. On any failure (501 while plan
 * storage is not built, network errors) the local copy is kept and nothing is marked imported.
 */
export async function importLocalPlans(accountId: string): Promise<ImportStatus> {
  const pending = plansToImport(accountId, loadPlans());
  if (pending.length === 0) return "idle";
  try {
    const { data, response } = await api.POST("/plans/import", { body: { plans: pending.map(toPlanCreate) } });
    if (response.status === 501) return "unavailable";
    if (!response.ok) return "failed";
    // The server answers with the new plans in request order. They exist now, so every plan is
    // marked imported even if an id were missing (retrying would create them a second time).
    markImported(accountId, Object.fromEntries(pending.map((p, i) => [p.localId, data?.[i]?.id])));
    await copyAnswers(pending);
    return "imported";
  } catch {
    return "failed";
  }
}

const empty = (v: unknown) => v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);

/**
 * Issue #17 D2: what a logged-out student told the planner goes to the record at login, but
 * only where the record is empty. The working information is copied; each General Information
 * answer waits on the dashboard as a proposal for the student to accept. Best effort: a failure
 * keeps the local copy and never blocks the plan import.
 */
export async function copyAnswers(plans: readonly LocalPlan[]): Promise<void> {
  const notes = plans.map((p) => p.workingNotes?.trim()).filter((n): n is string => !!n);
  const answers = Object.assign({}, ...plans.map((p) => p.profileAnswers ?? {})) as Record<string, unknown>;
  if (!notes.length && !Object.keys(answers).length) return;
  try {
    const { data: record } = await api.GET("/me/profile");
    if (!record) return;
    if (notes.length && !record.has_working_notes) {
      await api.PATCH("/me/profile", { body: { working_notes: notes.join("\n") } });
    }
    for (const [field, value] of Object.entries(answers)) {
      if (empty(value) || !empty((record as Record<string, unknown>)[field])) continue;
      await api.POST("/me/profile/proposals", { body: { field, value } });
    }
  } catch {
    // Kept in the local plan; the student can still answer on the dashboard.
  }
}

export function useImportOnLogin(): ImportStatus {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ImportStatus>("idle");
  const tried = useRef<string | null>(null);
  const accountId = session?.account.id;

  useEffect(() => {
    if (!accountId || tried.current === accountId) return;
    tried.current = accountId;
    // No cleanup flag: StrictMode re-runs effects, and the import must run exactly once.
    setStatus("importing");
    void importLocalPlans(accountId).then((s) => {
      setStatus(s);
      if (s === "imported") void queryClient.invalidateQueries({ queryKey: ["plans"] });
    });
  }, [accountId, queryClient]);

  return status;
}
