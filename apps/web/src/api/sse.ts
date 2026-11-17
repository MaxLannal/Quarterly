import { api, ApiError, NotAvailableError } from "./client";
import type { AgentEvent, ChatRequest, GenerateRequest } from "./types";

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

async function* readEvents(stream: ReadableStream<Uint8Array>): AsyncGenerator<AgentEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += done ? "\n\n" : decoder.decode(value, { stream: true });
    const { events, rest } = parseSseChunk(buffer);
    buffer = rest;
    for (const raw of events) yield JSON.parse(raw) as AgentEvent;
    if (done) return;
  }
}

function checkStream(response: Response, stream: ReadableStream<Uint8Array> | null | undefined) {
  if (response.status === 501) throw new NotAvailableError();
  if (!response.ok || !stream) throw new ApiError(response.status, `Request failed (${response.status})`);
  return stream;
}

/** POST /agents/generate, yielding each AgentEvent as it arrives. */
export async function* streamGenerate(body: GenerateRequest, signal?: AbortSignal) {
  const { data, response } = await api.POST("/agents/generate", { body, parseAs: "stream", signal });
  yield* readEvents(checkStream(response, data));
}

/** POST /agents/chat, yielding each AgentEvent as it arrives. */
export async function* streamChat(body: ChatRequest, signal?: AbortSignal) {
  const { data, response } = await api.POST("/agents/chat", { body, parseAs: "stream", signal });
  yield* readEvents(checkStream(response, data));
}
