import { api, ApiError, NotAvailableError } from "@/api/client";
import { checkStream, readSse } from "@/api/sse";
import type { AskEvent, AskRequest } from "./types";

/** POST /agents/ask, yielding each AskEvent as it arrives. */
export async function* streamAsk(body: AskRequest, signal?: AbortSignal): AsyncGenerator<AskEvent> {
  const { data, response } = await api.POST("/agents/ask", { body, parseAs: "stream", signal });
  yield* readSse<AskEvent>(checkStream(response, data));
}

/** What to tell the student when a question could not be sent. */
export function askErrorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "You have asked a lot today. Take a break and try again later.";
    if (error.status === 401 || error.status === 403) return "Your session changed. Reload the page and ask again.";
    if (error.status === 422) return "That question could not be sent. Try shortening it.";
    if (error.status >= 500) return "The guide is having trouble on our side. Try again.";
  }
  if (error instanceof NotAvailableError) return "The guide is not available yet.";
  if (error instanceof TypeError) return "You seem to be offline. Check your connection and try again.";
  return "Something went wrong. Try again.";
}
