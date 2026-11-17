import { useMemo } from "react";
import type { AccountOut } from "@/features/auth/api";
import { useSession as useAuthSession } from "@/features/auth/session";

/**
 * Who is logged in, in the `{ data, isLoading }` shape the top nav, planner and plan list read.
 *
 * There is one source of truth: the store in `features/auth/session`, which login, sign-up and
 * logout update directly. (This used to be a separate cached query that nothing refreshed after
 * a login, so the top nav kept saying "Log in" and the planner acted logged out until a reload.)
 */
export function useSession(): { data: { account: AccountOut } | null; isLoading: boolean } {
  const session = useAuthSession();
  const account = session.status === "authenticated" ? session.account : null;
  const data = useMemo(() => (account ? { account } : null), [account]);
  return { data, isLoading: session.status === "loading" };
}
