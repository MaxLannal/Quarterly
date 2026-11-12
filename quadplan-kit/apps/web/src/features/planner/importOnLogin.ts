import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import { useSession } from "@/lib/session";
import { loadPlans, markImported, plansToImport, toPlanCreate } from "./localPlans";

export type ImportStatus = "idle" | "importing" | "imported" | "unavailable" | "failed";

/**
 * POST the local plans to /plans/import once a session exists. On any failure (501 while plan
 * storage is not built, network errors) the local copy is kept and nothing is marked imported.
 */
export async function importLocalPlans(accountId: string): Promise<ImportStatus> {
  const pending = plansToImport(accountId, loadPlans());
  if (pending.length === 0) return "idle";
  try {
    const { response } = await api.POST("/plans/import", { body: { plans: pending.map(toPlanCreate) } });
    if (response.status === 501) return "unavailable";
    if (!response.ok) return "failed";
    markImported(
      accountId,
      pending.map((p) => p.localId),
    );
    return "imported";
  } catch {
    return "failed";
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
