/** Aliases for the Ask chatbot's generated OpenAPI types (never hand-written; `make api-client`). */
import type { components } from "@/api/schema";

type S = components["schemas"];

export type AskRequest = S["AskRequest"];
export type AskContext = S["AskContext"];
export type AskEvent = S["AskEvent"];
export type AskAnswerEvent = S["AskAnswerEvent"];
export type AskStepEvent = S["AskStepEvent"];
export type AskCitation = S["AskCitation"];
export type AskCourse = S["AskCourse"];
export type AskMode = NonNullable<AskRequest["mode"]>;

/** One line of the live agent trace ("Searching the catalog for “quantum”"). */
export interface TraceStep {
  tool: string;
  label: string;
  status: AskStepEvent["status"];
}

export interface UserTurn {
  id: string;
  role: "user";
  text: string;
}

export interface AssistantTurn {
  id: string;
  role: "assistant";
  /** "streaming" only while a request runs; a reload turns it into "stopped". */
  status: "streaming" | "done" | "error" | "stopped";
  text: string;
  citations: AskCitation[];
  courses: AskCourse[];
  followups: string[];
  /** False when the AI was resting and a plain search answered. */
  ai: boolean;
  steps: TraceStep[];
  error?: string;
  /** The student's own helpful / not helpful mark (kept in this browser only). */
  feedback?: "up" | "down" | null;
}

export type Turn = UserTurn | AssistantTurn;

export interface Conversation {
  id: string;
  title: string;
  /** Milliseconds; local to this browser, used only for ordering. */
  updatedAt: number;
  turns: Turn[];
}
