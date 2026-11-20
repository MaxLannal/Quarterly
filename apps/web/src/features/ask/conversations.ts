/**
 * Conversations with the campus guide, kept in this browser only (localStorage): the Ask page
 * under `quarterly.ask.v1`, the companion under `quarterly.companion.v1`. Nothing here is sent
 * to the server except the last turns of the conversation being continued.
 */
import { readJson, writeJson } from "@/lib/storage";
import type { AskCitation, AskCourse, AssistantTurn, Conversation, TraceStep, Turn } from "./types";

export const ASK_KEY = "quarterly.ask.v1";
export const COMPANION_KEY = "quarterly.companion.v1";
export const MAX_CONVERSATIONS = 40;
export const MAX_TURNS = 60;
/** The API takes at most 12 earlier turns of at most 4000 characters each. */
export const HISTORY_TURNS = 12;
export const MAX_CHARS = 4000;

interface Stored {
  version: 1;
  conversations: Conversation[];
}

export function newId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

/** A conversation's title: its first question, cut at a word near 60 characters. */
export function titleFrom(text: string): string {
  const one = text.replace(/\s+/g, " ").trim();
  if (one.length <= 60) return one || "New conversation";
  const cut = one.slice(0, 60);
  const space = cut.lastIndexOf(" ");
  return `${(space > 30 ? cut.slice(0, space) : cut).replace(/[,.;:!?-]+$/, "")}…`;
}

function isTurn(t: unknown): t is Turn {
  if (!t || typeof t !== "object") return false;
  const turn = t as { role?: unknown; text?: unknown; id?: unknown };
  return (turn.role === "user" || turn.role === "assistant") && typeof turn.text === "string" && typeof turn.id === "string";
}

/** Reads the stored conversations, newest first; anything malformed is dropped. A turn that was
 * still streaming when the page closed reads as stopped. */
export function loadConversations(key: string): Conversation[] {
  const stored = readJson<Stored>(key);
  if (!stored || stored.version !== 1 || !Array.isArray(stored.conversations)) return [];
  return stored.conversations
    .filter((c) => c && typeof c.id === "string" && Array.isArray(c.turns))
    .map((c) => ({
      id: c.id,
      title: typeof c.title === "string" && c.title ? c.title : "Conversation",
      updatedAt: typeof c.updatedAt === "number" ? c.updatedAt : 0,
      turns: c.turns.filter(isTurn).map((t) =>
        t.role === "assistant"
          ? {
              ...t,
              status: t.status === "streaming" ? "stopped" : t.status,
              citations: Array.isArray(t.citations) ? t.citations : [],
              courses: Array.isArray(t.courses) ? t.courses : [],
              followups: Array.isArray(t.followups) ? t.followups : [],
              steps: Array.isArray(t.steps) ? t.steps : [],
            }
          : t,
      ),
    }))
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, MAX_CONVERSATIONS);
}

export function saveConversations(key: string, conversations: Conversation[]): boolean {
  const trimmed = conversations
    .slice(0, MAX_CONVERSATIONS)
    .map((c) => ({ ...c, turns: c.turns.slice(-MAX_TURNS) }));
  return writeJson(key, { version: 1, conversations: trimmed } satisfies Stored);
}

/** The earlier turns to send with a new question: answered turns only, the last 12. */
export function historyOf(turns: Turn[]): { role: "user" | "assistant"; text: string }[] {
  const out: { role: "user" | "assistant"; text: string }[] = [];
  for (const t of turns) {
    if (t.role === "assistant" && t.status !== "done") continue;
    if (!t.text.trim()) continue;
    out.push({ role: t.role, text: t.text.slice(0, MAX_CHARS) });
  }
  return out.slice(-HISTORY_TURNS);
}

/** A step event merged into the trace: "done" or "failed" closes the matching started step. */
export function mergeStep(steps: TraceStep[], step: TraceStep): TraceStep[] {
  if (step.status !== "started") {
    for (let i = steps.length - 1; i >= 0; i--) {
      const s = steps[i] as TraceStep;
      if (s.tool === step.tool && s.label === step.label && s.status === "started") {
        return [...steps.slice(0, i), { ...s, status: step.status }, ...steps.slice(i + 1)];
      }
    }
  }
  return [...steps, step];
}

export function pendingAnswer(): AssistantTurn {
  return {
    id: newId(),
    role: "assistant",
    status: "streaming",
    text: "",
    citations: [] as AskCitation[],
    courses: [] as AskCourse[],
    followups: [],
    ai: true,
    steps: [],
    feedback: null,
  };
}
