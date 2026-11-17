import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "@/api/schema";

export type AccountOut = components["schemas"]["AccountOut"];
export type SessionOut = components["schemas"]["SessionOut"];
export type AccountExport = components["schemas"]["AccountExport"];

/** The session's CSRF token (from SessionOut). Kept in memory only. */
let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/** Adds `X-CSRF-Token` to state-changing requests; the API refuses them without it. */
export const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    if (csrfToken && !SAFE_METHODS.has(request.method)) {
      request.headers.set("X-CSRF-Token", csrfToken);
    }
    return request;
  },
};

export const api = createClient<paths>({
  baseUrl: `${window.location.origin}/api`,
  credentials: "same-origin",
  // Looked up at call time so tests can replace the global.
  fetch: (request) => globalThis.fetch(request),
});
api.use(csrfMiddleware);

export type Result<T> = { ok: true; data: T } | { ok: false; status: number; message: string };

const GENERIC = "Something went wrong. Try again.";
const OFFLINE = "Could not reach the server. Check your connection and try again.";

function detailOf(error: unknown): string | null {
  if (typeof error !== "object" || error === null || !("detail" in error)) return null;
  const detail = (error as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first: unknown = detail[0];
    if (typeof first === "object" && first !== null && "msg" in first) {
      const msg = (first as { msg: unknown }).msg;
      if (typeof msg === "string") return msg;
    }
  }
  return null;
}

/** Runs a generated-client call and folds network failures and API errors into one shape. */
export async function attempt<T>(
  call: () => Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<Result<T>> {
  try {
    const { data, error, response } = await call();
    if (response.ok) return { ok: true, data: data as T };
    return { ok: false, status: response.status, message: detailOf(error) ?? GENERIC };
  } catch {
    return { ok: false, status: 0, message: OFFLINE };
  }
}
