/**
 * MSW handlers for the agent endpoints (prompt 07): `/agents/generate`, `/agents/chat` and the
 * chat history. Vitest and Playwright e2e only (VITE_MOCK_API=1); the real app streams from the
 * API. They follow the server's event order and behavior, without a model:
 * - generate: the step names of the harness, variants with a rationale, then `done`;
 * - chat: a fixed refusal for off-topic questions, an answer with citations, a proposal card
 *   when asked to add something, and a `confirm` event for "apply it" / "I agree to ...".
 */
import { http, HttpResponse } from "msw";
import type { components } from "@/api/schema";
import type { AgentEvent, ChangeOp, ChangeSet, PlanState } from "@/api/types";
import { applyOps } from "@/features/planner/changes";
import { termAt } from "@/features/planner/terms";
import { mockVerify } from "./verify";

type S = components["schemas"];
const A = "*/api";

export function sse(events: AgentEvent[]) {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream" } });
}

const STEPS = ["Loading requirements", "Choosing electives", "Solving", "Verifying", "Writing rationale"];

function firstFreeTerms(plan: PlanState, n: number): string[] {
  const used = new Set((plan.items ?? []).map((i) => i.term));
  const out: string[] = [];
  for (let y = 1; y <= 4 && out.length < n; y += 1) {
    for (const q of ["AU", "WI", "SP"] as const) {
      const t = termAt(plan.entry_term, y, q);
      if (!used.has(t) && out.length < n) out.push(t);
    }
  }
  return out;
}

export function generateVariants(req: S["GenerateRequest"]): AgentEvent[] {
  const events: AgentEvent[] = [];
  for (const name of STEPS) {
    events.push({ type: "step", name, status: "started" });
    events.push({ type: "step", name, status: "done" });
  }
  const labels = ["Fake balanced", "Fake front-loaded", "Fake light start"];
  const planned = new Set((req.plan.items ?? []).map((i) => i.course));
  const candidates = ["TEST 10000", "TEST 10100", "TEST 10200", "FAKE 11000", "FAKE 11100", "FAKE 11200"].filter((c) => !planned.has(c));
  const terms = firstFreeTerms(req.plan, 3);
  for (let v = 0; v < Math.min(Math.max(req.variants ?? 2, 1), 3); v += 1) {
    const ops: ChangeOp[] = candidates.slice(0, 3).map((course, i) => ({
      op: "add",
      course,
      slot_ref: null,
      term: terms[(i + v) % Math.max(terms.length, 1)] ?? req.plan.entry_term,
      status: "planned",
      grading: "letter",
      locked: false,
      units: null,
    }));
    const after = applyOps(req.plan, ops);
    const rationale: Record<string, string> = {};
    for (const op of ops) if (op.op === "add") rationale[op.term] = `Fake rationale: places ${op.course} here.`;
    events.push({
      type: "variant",
      label: labels[v] ?? `Fake variant ${v + 1}`,
      change_set: { id: req.plan_id ? `fake-cs-${v + 1}` : null, plan_id: req.plan_id ?? null, origin: "generate", ops, base_plan_hash: "mock", status: "proposed", preview_report: null },
      report: mockVerify(after),
      metrics: { avg_hours: 9 + v, hardest_quarter_hours: 18 + v },
      rationale,
      citations: [{ kind: "course", id: ops[0]?.op === "add" ? (ops[0].course ?? "TEST 10000") : "TEST 10000", label: "Fake source" }],
    });
  }
  events.push({ type: "done", run_id: "fake-run" });
  return events;
}

const AFFIRM = /^(yes,?\s+)?(apply( it)?|i agree|confirm)[.!]?$/i;

export function chatReply(req: S["ChatRequest"]): AgentEvent[] {
  const msg = req.message.trim();
  const done: AgentEvent = { type: "done", run_id: "fake-run" };
  if (AFFIRM.test(msg)) {
    const latest = req.latest_proposal as ChangeSet | null | undefined;
    if (!latest) return [{ type: "message", text: "There is no proposal to apply yet.", citations: [] }, done];
    return [{ type: "confirm", change_set: latest, confirmation_text: msg }, done];
  }
  if (/weather|joke|recipe|essay/i.test(msg)) {
    return [{ type: "message", text: "I can only help with planning your courses.", citations: [] }, done];
  }
  const events: AgentEvent[] = [
    {
      type: "message",
      text: "Mock advisor: TEST 25200 is a lighter elective than TEST 25000 in this fake data.",
      citations: [
        { kind: "attribute", id: "TEST 25200:workload_hours", label: "TEST 25200 · workload 13 h/wk · n=34" },
        { kind: "course", id: "TEST 25200", label: "TEST 25200" },
        // Forum sources name only an id, like the API (labels as `citation_label` builds them):
        // post 3 and page 1 are the fake discussion thread and page in mocks/forum.ts.
        { kind: "post", id: "3", label: "Student post #3" },
        { kind: "summary", id: "1", label: "What students say" },
      ],
    },
  ];
  if (/\badd\b/i.test(msg)) {
    const term = firstFreeTerms(req.plan, 1)[0] ?? req.plan.entry_term;
    const ops: ChangeOp[] = [{ op: "add", course: "TEST 25200", slot_ref: null, term, status: "planned", grading: "letter", locked: false, units: null }];
    events.push({
      type: "proposal",
      change_set: { id: req.plan_id ? "fake-chat-cs-1" : null, plan_id: req.plan_id ?? null, origin: "chat", ops, base_plan_hash: "mock", status: "proposed", preview_report: mockVerify(applyOps(req.plan, ops)) },
    });
  }
  events.push(done);
  return events;
}

export const agentHandlers = [
  http.post(`${A}/agents/generate`, async ({ request }) => sse(generateVariants((await request.json()) as S["GenerateRequest"]))),
  http.post(`${A}/agents/chat`, async ({ request }) => sse(chatReply((await request.json()) as S["ChatRequest"]))),
  http.get(`${A}/agents/chat/history`, () => HttpResponse.json({ run_id: null, entries: [] } satisfies S["ChatHistory"])),
];
