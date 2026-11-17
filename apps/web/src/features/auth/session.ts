import { useEffect, useSyncExternalStore } from "react";
import { api, attempt, setCsrfToken, type AccountOut, type SessionOut } from "./api";

export type SessionState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; account: AccountOut };

let state: SessionState = { status: "loading" };
let loading: Promise<void> | null = null;
const listeners = new Set<() => void>();

function set(next: SessionState) {
  state = next;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Call with the SessionOut from register or login. */
export function signedIn(session: SessionOut) {
  setCsrfToken(session.csrf_token);
  set({ status: "authenticated", account: session.account });
}

export function signedOut() {
  setCsrfToken(null);
  set({ status: "anonymous" });
}

/** Asks the API who is logged in (once per page load unless `force`). */
export function loadSession(force = false): Promise<void> {
  if (loading && !force) return loading;
  loading = attempt(() => api.GET("/auth/session")).then((result) => {
    if (result.ok && result.data?.account) signedIn(result.data);
    else signedOut();
  });
  return loading;
}

export function useSession(): SessionState {
  const current = useSyncExternalStore(subscribe, () => state);
  useEffect(() => {
    void loadSession();
  }, []);
  return current;
}

/** Test helper: forget everything. */
export function resetSession() {
  loading = null;
  setCsrfToken(null);
  state = { status: "loading" };
}
