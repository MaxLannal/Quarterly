import { api, ApiError, NotAvailableError } from "./client";
import type { PlannerEvent, PlannerRequest } from "./types";

/**
 * Splits a Server-Sent Events text stream into the JSON payloads of its `data:` lines.
 * Events are separated by a blank line; multi-line data is joined with "\n".
 */
export function parseSseChunk(buffer: string): { events: string[]; rest: string } {
  const normalised = buffer.replace(/\r\n/g, "\n");
  const blocks = normalised.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: string[] = [];
  for (const block of blocks) {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).replace(/^ /, ""));
    if (data.length) events.push(data.join("\n"));
  }
  return { events, rest };
}

/** Reads a text/event-stream body as JSON events of type `T` (any SSE endpoint's own union). */
export async function* readSse<T>(stream: ReadableStream<Uint8Array>): AsyncGenerator<T> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += done ? "\n\n" : decoder.decode(value, { stream: true });
    const { events, rest } = parseSseChunk(buffer);
    buffer = rest;
    for (const raw of events) yield JSON.parse(raw) as T;
    if (done) return;
  }
}

/** The body of a streamed response, or the error the request failed with. */
export function checkStream(response: Response, stream: ReadableStream<Uint8Array> | null | undefined) {
  if (response.status === 501) throw new NotAvailableError();
  if (!response.ok || !stream) throw new ApiError(response.status, `Request failed (${response.status})`);
  return stream;
}

/** A planner request: the mode and the plan, the rest optional (the server has defaults). */
export type PlannerBody = Pick<PlannerRequest, "mode" | "plan"> & Partial<Omit<PlannerRequest, "mode" | "plan">>;

/** POST /agents/planner (issue #17), yielding each PlannerEvent as it arrives. */
export async function* streamPlanner(body: PlannerBody, signal?: AbortSignal): AsyncGenerator<PlannerEvent> {
  const full: PlannerRequest = { history: [], pending: [], profile_answers: {}, ...body };
  const { data, response } = await api.POST("/agents/planner", { body: full, parseAs: "stream", signal });
  yield* readSse<PlannerEvent>(checkStream(response, data));
}
