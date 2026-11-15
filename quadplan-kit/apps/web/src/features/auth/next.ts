import { useLocation } from "react-router-dom";

const DEFAULT = "/plan";

/**
 * Where to go after logging in or signing up (P08-10: back to the page the student came from).
 * Only a path on this site is accepted, so a crafted link cannot send anyone elsewhere.
 */
export function safeNext(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return DEFAULT;
  if (raw.startsWith("/login") || raw.startsWith("/signup")) return DEFAULT;
  return raw;
}

function withNext(page: "/login" | "/signup", from: string): string {
  const next = safeNext(from);
  return next === DEFAULT && from !== DEFAULT ? page : `${page}?next=${encodeURIComponent(next)}`;
}

/** Links to the login and sign-up pages that come back to the current page afterwards. */
export function useAuthLinks(): { login: string; signup: string } {
  const location = useLocation();
  const from = location.pathname + location.search;
  return { login: withNext("/login", from), signup: withNext("/signup", from) };
}
