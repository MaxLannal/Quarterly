import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { SessionOut } from "@/api/types";

export const SESSION_KEY = ["session"] as const;

/**
 * The current session, or null when logged out (401) or when accounts are not available yet (501).
 * Prompt 04 owns the auth pages; the shell and the plan import only need this read.
 */
export async function fetchSession(): Promise<SessionOut | null> {
  try {
    const { data, response } = await api.GET("/auth/session");
    return response.status === 200 && data ? data : null;
  } catch {
    return null;
  }
}

export function useSession() {
  return useQuery({ queryKey: SESSION_KEY, queryFn: fetchSession, staleTime: 60_000, retry: false });
}
