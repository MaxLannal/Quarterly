/** The planner panel's conversation as the page keeps it (a local plan stores it). */
import type { Citation, PlanEvent, QuestionEvent } from "@/api/types";

export type ThreadEntry =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string; citations: Citation[] }
  | { kind: "steps"; runId: string; steps: { name: string; status: "started" | "done" | "failed" }[] }
  | { kind: "question"; event: QuestionEvent; answered?: string }
  | { kind: "plan"; event: PlanEvent }
  | { kind: "proposal"; proposalId: string }
  | { kind: "error"; text: string; reason?: string | null };
