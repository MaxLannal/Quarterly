/**
 * MSW handlers for the planner agent (issues #17 and #18): `POST /agents/planner` and the chat
 * history. Vitest and Playwright e2e only (VITE_MOCK_API=1); the real app streams from the API.
 * They follow the server's event order without a model, on the fake 2099-00 catalog:
 * - generate: with no interests in the request, a `question` for them, then `done`. With
 *   interests (or a resumed run), the steps, a valid `plan`, three groups as proposals whose
 *   reasons name the student's first interest, then `done`;
 * - chat: a fixed refusal for off-topic questions, an answer with citations, a proposal when
 *   asked to add something or to replace "Language and the Human", "I hate <code>" notes a
 *   preference, and a `confirm` event for "apply it".
 */
import { http, HttpResponse } from "msw";
import type { components } from "@/api/schema";
import type { ChangeOp, PlanState, PlannerEvent } from "@/api/types";
import { applyOps } from "@/features/planner/changes";
import { termAt } from "@/features/planner/terms";
import { mockVerify } from "./verify";

type S = components["schemas"];
type Req = Partial<S["PlannerRequest"]> & Pick<S["PlannerRequest"], "mode" | "plan">;
const A = "*/api";

export function sse(events: PlannerEvent[]) {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream" } });
}

const RUN = "fake-planner-run";
const done = (extra: Partial<S["DoneEvent"]> = {}): PlannerEvent => ({ type: "done", run_id: RUN, ...extra });
const step = (name: string, status: "started" | "done"): PlannerEvent => ({ type: "step", name, status });
const VERDICT: S["Verdict"] = { status_after: "valid", status_before: "errors", new_issues: [], resolved_issues: 1 };

function add(course: string, term: string): ChangeOp {
  return { op: "add", course, slot_ref: null, term, status: "planned", grading: "letter", locked: false, units: null };
}

function interestOf(req: Req): string | null {
  const given = req.profile_answers?.interests;
  if (Array.isArray(given) && given.length) return String(given[0]);
  if (req.answer?.question_id === "interests") return (req.answer.text ?? req.answer.option ?? "").split(",")[0]?.trim() || null;
  return null;
}

/** The fake groups: an introductory sequence, a methods pair and two electives. */
const GROUPS: { id: string; title: string; kind: S["PlannerProposalEvent"]["kind"]; courses: [string, number, "AU" | "WI" | "SP"][]; rule: S["RuleRef"] }[] = [
  {
    id: "g1",
    title: "Test introductory sequence",
    kind: "major",
    courses: [["TEST 10000", 1, "AU"], ["TEST 10100", 1, "WI"], ["TEST 10200", 1, "SP"]],
    rule: { id: "G38", text: "Start the introductory sequence in year 1." },
  },
  {
    id: "g2",
    title: "Test methods",
    kind: "core",
    courses: [["TEST 20000", 2, "AU"], ["TEST 20100", 2, "WI"]],
    rule: { id: "G27", text: "Finish the Core by the end of the second year." },
  },
  {
    id: "g3",
    title: "Electives for testing",
    kind: "elective",
    courses: [["TEST 25000", 2, "SP"], ["TEST 25100", 3, "AU"]],
    rule: { id: "G22", text: "Spend free electives and major electives on the student's interests, career plan and research areas." },
  },
];

export function plannerGenerate(req: Req): PlannerEvent[] {
  const interest = interestOf(req);
  const events: PlannerEvent[] = [step("Reading your information", "started"), step("Reading your information", "done")];
  if (!interest) {
    events.push(
      { type: "question", run_id: RUN, question_id: "interests", field: "interests", text: "Which subjects or topics interest you most?", options: [], allow_other: true },
      done(),
    );
    return events;
  }
  for (const name of ["Checking what can fit", "Writing your plan", "Checking the plan", "Explaining each choice"]) {
    events.push(step(name, "started"), step(name, "done"));
  }
  events.push({ type: "plan", run_id: RUN, verdict: "valid", issues: [], compromises: [], summary: "Seven courses in three groups." });
  const have = new Set((req.plan.items ?? []).map((i) => i.course));
  GROUPS.forEach((g, n) => {
    const ops = g.courses.filter(([c]) => !have.has(c)).map(([c, y, q]) => add(c, termAt(req.plan.entry_term, y, q)));
    if (!ops.length) return;
    events.push({
      type: "proposal",
      change_set_id: req.plan_id ? `fake-planner-cs-${n + 1}` : null,
      group_id: g.id,
      title: g.title,
      kind: g.kind,
      ops,
      why: `You said you are interested in ${interest}. ${g.title} builds toward it, in the quarters these courses are offered.`,
      citations: [
        { kind: "profile", id: "interests", label: "Your interests" },
        { kind: "course", id: g.courses[0]![0], label: g.courses[0]![0] },
      ],
      rules: [g.rule],
      preview: VERDICT,
    });
  });
  events.push(done(req.answer ? { profile_answers: { interests: [interest] } } : {}));
  return events;
}

const AFFIRM = /^(yes,?\s+)?(apply( it)?|i agree|confirm)[.!]?$/i;

function firstFreeTerm(plan: PlanState): string {
  const used = new Set((plan.items ?? []).map((i) => i.term));
  for (let y = 1; y <= 4; y += 1) {
    for (const q of ["AU", "WI", "SP"] as const) {
      const t = termAt(plan.entry_term, y, q);
      if (!used.has(t)) return t;
    }
  }
  return plan.entry_term;
}

export function plannerChat(req: Req): PlannerEvent[] {
  const msg = (req.message ?? "").trim();
  if (AFFIRM.test(msg)) {
    const latest = req.pending?.at(-1);
    if (!latest) return [{ type: "message", text: "There is no proposal to apply yet.", citations: [] }, done()];
    return [{ type: "confirm", change_set: { origin: "chat", ops: latest.ops, base_plan_hash: latest.base_plan_hash, status: "proposed" }, confirmation_text: msg }, done()];
  }
  if (/weather|joke|recipe|essay/i.test(msg)) {
    return [{ type: "message", text: "I can only help with planning your courses.", citations: [] }, done()];
  }
  const hate = /\bI hate (TEST \d{5})/i.exec(msg);
  if (hate) {
    const code = hate[1]!.toUpperCase();
    const notes = [req.working_notes, `- 2026-11-26 · avoid · ${msg} [${code}]`].filter(Boolean).join("\n");
    return [{ type: "message", text: `Noted: I will not propose ${code} again.`, citations: [] }, done({ working_notes: notes })];
  }
  const events: PlannerEvent[] = [
    {
      type: "message",
      text: "Mock planner: TEST 25200 is a lighter elective than TEST 25000 in this fake data.",
      citations: [
        { kind: "attribute", id: "TEST 25200:workload_hours", label: "TEST 25200 · workload 13 h/wk · n=34" },
        { kind: "course", id: "TEST 25200", label: "TEST 25200" },
        { kind: "guideline", id: "G22", label: "Guideline G22" },
      ],
    },
  ];
  if (/\badd\b|language and the human/i.test(msg)) {
    const ops = [add("TEST 25200", firstFreeTerm(req.plan))];
    const core = /language and the human/i.test(msg);
    events.push({
      type: "proposal",
      change_set_id: req.plan_id ? "fake-chat-cs-1" : null,
      group_id: "chat-1",
      title: core ? "A new Core choice: TEST 25200" : "Add TEST 25200",
      kind: core ? "core" : "elective",
      ops,
      why: "It is lighter than TEST 25000 and keeps your plan on track.",
      citations: [],
      rules: [{ id: "G22", text: "Spend free electives and major electives on the student's interests, career plan and research areas." }],
      preview: { status_after: mockVerify(applyOps(req.plan, ops)).status, status_before: "warnings", new_issues: [], resolved_issues: 0 },
    });
  }
  events.push(done());
  return events;
}

export const agentHandlers = [
  http.post(`${A}/agents/planner`, async ({ request }) => {
    const req = (await request.json()) as Req;
    return sse(req.mode === "chat" ? plannerChat(req) : plannerGenerate(req));
  }),
  http.get(`${A}/agents/planner/history`, () => HttpResponse.json({ run_id: null, entries: [] } satisfies S["ChatHistory"])),
  http.delete(`${A}/agents/planner/history`, () => new HttpResponse(null, { status: 204 })),
];
