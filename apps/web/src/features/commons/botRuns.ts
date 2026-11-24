/**
 * The bot's runs on this page session, outside React: a run keeps going when its card unmounts
 * (React's development double-mount, or the student scrolling or navigating away), because the
 * server only stores the answer when the stream finishes. Cards subscribe with `useBotRun`.
 */
import type { QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { commonsKeys, streamBot, type BotRequest, type Reply } from "./api";

export interface BotStep {
  tool: string;
  label: string;
  status: "started" | "done" | "failed";
}

export interface BotRunState {
  status: "running" | "busy" | "done" | "error";
  steps: BotStep[];
  reply?: Reply;
  fallback?: boolean;
  error?: string;
}

const runs = new Map<string, BotRunState>();
const listeners = new Set<() => void>();

export function runKey(threadId: number, replyTo?: number | null): string {
  return `${threadId}:${replyTo ?? "top"}`;
}

function set(key: string, state: BotRunState) {
  runs.set(key, state);
  for (const l of listeners) l();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useBotRun(key: string): BotRunState | undefined {
  return useSyncExternalStore(
    subscribe,
    () => runs.get(key),
    () => undefined,
  );
}

export function botRunStarted(key: string): boolean {
  return runs.has(key);
}

/** Poll the thread while another request writes the answer (up to a minute). */
function pollUntilAnswered(client: QueryClient, threadId: number, key: string, tries = 0) {
  window.setTimeout(async () => {
    await client.invalidateQueries({ queryKey: commonsKeys.thread(threadId) });
    const detail = client.getQueryData<{ has_bot_answer?: boolean; bot_state?: string }>(commonsKeys.thread(threadId));
    const state = runs.get(key);
    if (detail?.has_bot_answer || detail?.bot_state === "answered") {
      if (state) set(key, { ...state, status: "done" });
      return;
    }
    if (tries < 20) pollUntilAnswered(client, threadId, key, tries + 1);
    else if (state) set(key, { ...state, status: "error", error: "The AI is taking a while. Reload in a minute." });
  }, 3000);
}

/** Start the bot on a thread (or under a reply that summoned it), unless it is already running. */
export function startBotRun(client: QueryClient, threadId: number, request: Partial<BotRequest> = {}): void {
  const body: BotRequest = { regenerate: false, reply_to: null, ...request };
  const key = runKey(threadId, body.reply_to);
  if (runs.get(key)?.status === "running") return;
  let state: BotRunState = { status: "running", steps: [] };
  set(key, state);
  void (async () => {
    try {
      for await (const event of streamBot(threadId, body)) {
        if (event.type === "step") {
          const steps = [...state.steps];
          const open = steps.findIndex((s) => s.tool === event.tool && s.label === event.label && s.status === "started");
          if (event.status !== "started" && open >= 0) steps[open] = { tool: event.tool, label: event.label, status: event.status };
          else steps.push({ tool: event.tool, label: event.label, status: event.status });
          state = { ...state, steps };
        } else if (event.type === "answer") {
          state = { ...state, status: "done", reply: event.reply, fallback: event.fallback };
        } else if (event.type === "busy") {
          state = { ...state, status: "busy" };
          pollUntilAnswered(client, threadId, key);
        } else if (event.type === "error") {
          state = { ...state, status: "error", error: event.message };
        }
        set(key, state);
      }
      if (state.status === "running") state = { ...state, status: "error", error: "The AI stopped before answering. Try again." };
      set(key, state);
    } catch (e) {
      set(key, { ...state, status: "error", error: e instanceof Error ? e.message : "The AI could not answer right now." });
    }
    if (state.status === "done") {
      await client.invalidateQueries({ queryKey: commonsKeys.thread(threadId) });
      void client.invalidateQueries({ queryKey: ["commons", "list"] });
    }
  })();
}

/** Forget a finished run (a retry or a regenerate starts afresh). */
export function clearBotRun(key: string): void {
  if (runs.get(key)?.status !== "running") {
    runs.delete(key);
    for (const l of listeners) l();
  }
}
