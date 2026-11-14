import createClient from "openapi-fetch";
import { csrfMiddleware } from "@/features/auth/api";
import type { paths } from "./schema";

/** The API lives under `/api` on the same origin (Vite proxy in dev, nginx in Docker). */
function apiBase(): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost";
  return `${origin}/api`;
}

/**
 * Typed client generated from the OpenAPI document. `fetch` is looked up at call time so MSW
 * (which patches `globalThis.fetch` in tests) always sees the request.
 */
export const api = createClient<paths>({
  baseUrl: apiBase(),
  credentials: "same-origin",
  fetch: (request: Request) => globalThis.fetch(request),
});
// State-changing requests carry the session's CSRF token (the API refuses them otherwise).
api.use(csrfMiddleware);

/** Thrown when an endpoint answers 501: the feature exists in the contract but not on the server yet. */
export class NotAvailableError extends Error {
  constructor(message = "This feature is not available yet.") {
    super(message);
    this.name = "NotAvailableError";
  }
}

/** Any other failed request. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailOf(error: unknown): string | undefined {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return undefined;
}

/**
 * Unwraps an openapi-fetch result: returns `data` or throws `NotAvailableError` (501) /
 * `ApiError` (anything else that is not 2xx).
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  const { data, error, response } = result;
  if (response.status === 501) throw new NotAvailableError(detailOf(error));
  if (!response.ok || data === undefined) {
    throw new ApiError(response.status, detailOf(error) ?? `Request failed (${response.status})`);
  }
  return data;
}

export function isNotAvailable(error: unknown): boolean {
  return error instanceof NotAvailableError;
}
