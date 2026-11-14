/**
 * MSW handlers for every API endpoint, typed with the generated OpenAPI schema. On in vitest,
 * in Playwright e2e (VITE_MOCK_API=1 build) and in dev with VITE_MOCK_API=1. The real app calls
 * the real API. Every handler here is listed in docs/OPEN_QUESTIONS.md "Prompt 03 mocks".
 */
import { http, HttpResponse } from "msw";
import type { components } from "@/api/schema";
import type { AgentEvent, ChangeOp, PlanState } from "@/api/types";
import { applyOps } from "@/features/planner/changes";
import { termAt } from "@/features/planner/terms";
import {
  allCourses,
  CATALOG_YEARS,
  detail,
  findCourse,
  matches,
  MOCK_CATALOG_YEAR,
  mockTerms,
  programDetail,
  PROGRAMS,
  summary,
} from "./data";
import { forumHandlers, resetForumMock } from "./forum";
import { mockVerify } from "./verify";

type S = components["schemas"];
const A = "*/api";

function json<T>(body: T, status = 200) {
  return HttpResponse.json(body as never, { status });
}
const notFound = (what: string) => json<S["ErrorOut"]>({ detail: `${what} not found` }, 404);
const unauthorized = () => json<S["ErrorOut"]>({ detail: "Not logged in" }, 401);
const dec = (s: unknown) => decodeURIComponent(String(s));

// ------------------------------------------------------------------------------------------
// In-memory mock state (per page load / per test file). The session flag also lives in
// sessionStorage so a mock login survives a reload in e2e.
// ------------------------------------------------------------------------------------------

const MOCK_ACCOUNT: S["AccountOut"] = { id: "00000000-0000-4000-8000-000000000001", username: "fake-user", role: "user", created_day: "2099-01-01" };
const SESSION_FLAG = "quarterly.mock.session";
let memorySession = false;

function loggedIn(): boolean {
  try {
    return memorySession || globalThis.sessionStorage?.getItem(SESSION_FLAG) === "1";
  } catch {
    return memorySession;
  }
}
function setLoggedIn(v: boolean) {
  memorySession = v;
  try {
    if (v) globalThis.sessionStorage?.setItem(SESSION_FLAG, "1");
    else globalThis.sessionStorage?.removeItem(SESSION_FLAG);
  } catch {
    // ignore
  }
}
const session = (): S["SessionOut"] => ({ account: MOCK_ACCOUNT, csrf_token: "fake-csrf" });

const plans = new Map<string, S["PlanOut"]>();
let planSeq = 0;
/** Received /plans/import bodies, for tests. */
export const importedPlans: S["PlanCreate"][] = [];

function today() {
  return new Date().toISOString().slice(0, 10);
}
function makePlan(body: S["PlanCreate"]): S["PlanOut"] {
  planSeq += 1;
  const id = `00000000-0000-4000-8000-${String(planSeq).padStart(12, "0")}`;
  const plan: S["PlanOut"] = {
    id,
    name: body.name,
    is_primary: body.is_primary,
    catalog_year: body.state.catalog_year,
    entry_term: body.state.entry_term,
    state: body.state,
    plan_hash: `mock-${planSeq}`,
    updated_day: today(),
    report: null,
  };
  plans.set(id, plan);
  return plan;
}
const toSummary = (p: S["PlanOut"]): S["PlanSummary"] => ({
  id: p.id,
  name: p.name,
  is_primary: p.is_primary,
  catalog_year: p.catalog_year,
  entry_term: p.entry_term,
  updated_day: p.updated_day,
});

export function resetMockState() {
  plans.clear();
  importedPlans.length = 0;
  setLoggedIn(false);
  resetForumMock();
}

// ------------------------------------------------------------------------------------------
// Agents (SSE)
// ------------------------------------------------------------------------------------------

function sse(events: AgentEvent[]) {
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

function generateVariants(req: S["GenerateRequest"]): AgentEvent[] {
  const events: AgentEvent[] = [];
  for (const name of STEPS) {
    events.push({ type: "step", name, status: "started" });
    events.push({ type: "step", name, status: "done" });
  }
  const labels = ["Fake balanced", "Fake front-loaded", "Fake light start"];
  const planned = new Set((req.plan.items ?? []).map((i) => i.course));
  const candidates = ["TEST 10000", "TEST 10100", "TEST 10200", "FAKE 11000", "FAKE 11100", "FAKE 11200"].filter((c) => !planned.has(c));
  const terms = firstFreeTerms(req.plan, 3);
  for (let v = 0; v < Math.min(Math.max(req.variants, 1), 3); v += 1) {
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
      change_set: { id: `fake-cs-${v + 1}`, plan_id: req.plan_id ?? null, origin: "generate", ops, base_plan_hash: "mock", status: "proposed", preview_report: null },
      report: mockVerify(after),
      metrics: { avg_hours: 9 + v, hardest_quarter_hours: 18 + v },
      rationale,
    });
  }
  events.push({ type: "done", run_id: "fake-run" });
  return events;
}

function chatReply(req: S["ChatRequest"]): AgentEvent[] {
  const msg = req.message.toLowerCase();
  if (/weather|joke|recipe/.test(msg)) {
    return [{ type: "message", text: "I can only help with course planning.", citations: [] }, { type: "done", run_id: "fake-run" }];
  }
  const events: AgentEvent[] = [
    {
      type: "message",
      text: "Mock advisor: TEST 25200 is a lighter elective than TEST 25000 in this fake data.",
      citations: [
        { kind: "attribute", id: "TEST 25200:workload_hours", label: "TEST 25200 · workload 13 h/wk · n=34" },
        { kind: "course", id: "TEST 25200", label: "TEST 25200" },
      ],
    },
  ];
  if (msg.includes("add")) {
    const term = firstFreeTerms(req.plan, 1)[0] ?? req.plan.entry_term;
    const ops: ChangeOp[] = [{ op: "add", course: "TEST 25200", slot_ref: null, term, status: "planned", grading: "letter", locked: false, units: null }];
    events.push({
      type: "proposal",
      change_set: { id: "fake-chat-cs-1", plan_id: req.plan_id ?? null, origin: "chat", ops, base_plan_hash: "mock", status: "proposed", preview_report: mockVerify(applyOps(req.plan, ops)) },
    });
  }
  events.push({ type: "done", run_id: "fake-run" });
  return events;
}

// ------------------------------------------------------------------------------------------
// Handlers
// ------------------------------------------------------------------------------------------

export const handlers = [
  ...forumHandlers, // forum, instructors and moderation: src/mocks/forum.ts (prompt 08)
  http.get(`${A}/health`, () => json<S["HealthOut"]>({ status: "ok", db: true, redis: true })),
  http.get(`${A}/version`, () => json<S["VersionOut"]>({ version: "mock", git_sha: "mock", core_version: "mock" })),

  // Catalog
  http.get(`${A}/catalog-years`, () => json<S["CatalogYearOut"][]>(CATALOG_YEARS)),
  http.get(`${A}/terms`, () => json<S["Term"][]>(mockTerms())),
  http.get(`${A}/courses`, ({ request }) => {
    const u = new URL(request.url);
    const q = (u.searchParams.get("q") ?? "").toLowerCase();
    const subject = u.searchParams.get("subject");
    const level = Number(u.searchParams.get("level") ?? 0);
    const quarter = u.searchParams.get("quarter");
    const core = u.searchParams.get("core_tag");
    const maxH = Number(u.searchParams.get("max_workload_hours") ?? Infinity);
    const maxD = Number(u.searchParams.get("max_difficulty") ?? Infinity);
    const limit = Number(u.searchParams.get("limit") ?? 20);
    const offset = Number(u.searchParams.get("offset") ?? 0);
    const hits = allCourses().filter((c) => {
      const num = Number(c.code.split(" ")[1]);
      return (
        (!q || c.code.toLowerCase().includes(q) || c.title.toLowerCase().includes(q)) &&
        (!subject || c.code.startsWith(`${subject} `)) &&
        (!level || Math.floor(num / 10000) * 10000 === level) &&
        (!quarter || c.quarters.includes(quarter as "AU")) &&
        (!core || (c.core_tags ?? []).includes(core)) &&
        (c.hours ?? 0) <= maxH &&
        (c.difficulty ?? 0) <= maxD
      );
    });
    return json<S["Page_CourseSummary_"]>({ items: hits.slice(offset, offset + limit).map(summary), total: hits.length, limit, offset });
  }),
  http.get(`${A}/courses/:code`, ({ params }) => {
    const c = findCourse(dec(params.code));
    if (!c) return notFound("Course");
    const d = detail(c);
    d.counts_toward = PROGRAMS.flatMap((p) => {
      const rules = programDetail(p.id)?.rules;
      if (rules?.kind !== "group") return [];
      return rules.children
        .filter((n) => (n.kind === "select" && matches(c.code, n.from)) || (n.kind === "slot" && n.any_of.includes(c.code)))
        .map((n) => ({ program_id: p.id, program_name: p.name, node_id: `${p.id}/${n.id}`, label: n.label ?? null }));
    });
    return json<S["CourseDetail"]>(d);
  }),
  http.get(`${A}/course-lists/:name`, ({ params }) =>
    json<S["CourseList"]>({ name: dec(params.name), label: "Fake list", courses: ["FAKE 11000", "FAKE 11100", "FAKE 11200"], sublists: [], needs_review: false, source: null }),
  ),
  http.get(`${A}/programs`, () => json<S["ProgramSummary"][]>(PROGRAMS)),
  http.get(`${A}/programs/:id/eligible`, ({ params, request }) => {
    const program = programDetail(dec(params.id));
    if (!program) return notFound("Program");
    const node = new URL(request.url).searchParams.get("node") ?? "";
    const target = findNode(program.rules, program.id, node);
    const sel = target;
    const items = allCourses().filter((c) => (sel ? sel(c.code) : false)).map(summary);
    return json<S["CourseSummary"][]>(items);
  }),
  http.get(`${A}/programs/:id`, ({ params }) => {
    const p = programDetail(dec(params.id));
    return p ? json<S["ProgramDetail"]>(p) : notFound("Program");
  }),

  // Verifier
  http.post(`${A}/verify`, async ({ request }) => {
    const body = (await request.json()) as S["VerifyRequest"];
    return json<S["Report"]>(mockVerify(body.plan));
  }),

  // Agents
  http.post(`${A}/plans/:id/generate`, async ({ params, request }) => {
    const options = (await request.json()) as S["GenerateOptions"];
    const saved = plans.get(String(params.id));
    if (!saved) return json<S["ErrorOut"]>({ detail: "Plan not found." }, 404);
    const events = generateVariants({ plan: saved.state, plan_id: String(params.id), variants: options.variants ?? 2 } as S["GenerateRequest"]);
    const variants = events.flatMap((e) =>
      e.type === "variant" ? [{ label: e.label, change_set: e.change_set, plan: saved.state, report: e.report, metrics: e.metrics, rationale: e.rationale }] : [],
    );
    return json<S["GenerateOut"]>({ variants, infeasible: null });
  }),
  http.post(`${A}/plans/generate`, async ({ request }) => {
    const body = (await request.json()) as S["GenerateLocal"];
    const events = generateVariants({ plan: body.plan, plan_id: null, variants: body.options?.variants ?? 2 } as S["GenerateRequest"]);
    const variants = events.flatMap((e) =>
      e.type === "variant" ? [{ label: e.label, change_set: e.change_set, plan: body.plan, report: e.report, metrics: e.metrics, rationale: e.rationale }] : [],
    );
    return json<S["GenerateOut"]>({ variants, infeasible: null });
  }),
  http.post(`${A}/agents/generate`, async ({ request }) => sse(generateVariants((await request.json()) as S["GenerateRequest"]))),
  http.post(`${A}/agents/chat`, async ({ request }) => sse(chatReply((await request.json()) as S["ChatRequest"]))),

  // Auth and account (prompt 04 builds the real ones)
  http.get(`${A}/auth/session`, () => (loggedIn() ? json<S["SessionOut"]>(session()) : unauthorized())),
  http.post(`${A}/auth/login`, () => {
    setLoggedIn(true);
    return json<S["SessionOut"]>(session());
  }),
  http.post(`${A}/auth/logout`, () => {
    setLoggedIn(false);
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(`${A}/auth/email`, () => json<S["EmailStarted"]>({ pending_id: "fake-pending" }, 202)),
  http.post(`${A}/auth/verify-code`, async ({ request }) => {
    const body = (await request.json()) as S["VerifyCode"];
    return body.code === "123456" ? json<S["RegistrationTicket"]>({ ticket: "fake-ticket" }) : json<S["ErrorOut"]>({ detail: "Wrong code" }, 400);
  }),
  http.post(`${A}/auth/register`, () => {
    setLoggedIn(true);
    return json<S["SessionOut"]>(session(), 201);
  }),
  http.post(`${A}/auth/password-reset/start`, () => json<S["EmailStarted"]>({ pending_id: "fake-pending" }, 202)),
  http.post(`${A}/auth/password-reset/finish`, () => new HttpResponse(null, { status: 204 })),
  http.get(`${A}/account/export`, () =>
    loggedIn() ? json<S["AccountExport"]>({ account: MOCK_ACCOUNT, plans: [...plans.values()] }) : unauthorized(),
  ),
  http.post(`${A}/account/password`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${A}/account/delete`, () => {
    setLoggedIn(false);
    return new HttpResponse(null, { status: 204 });
  }),

  // Plans (prompt 04/06)
  http.get(`${A}/plans`, () => (loggedIn() ? json<S["PlanSummary"][]>([...plans.values()].map(toSummary)) : unauthorized())),
  http.post(`${A}/plans`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    return json<S["PlanOut"]>(makePlan((await request.json()) as S["PlanCreate"]), 201);
  }),
  http.post(`${A}/plans/import`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    const body = (await request.json()) as S["PlanImport"];
    importedPlans.push(...body.plans);
    return json<S["PlanSummary"][]>(body.plans.map((p) => toSummary(makePlan(p))));
  }),
  http.get(`${A}/plans/compare`, ({ request }) => {
    const u = new URL(request.url);
    const a = plans.get(u.searchParams.get("a") ?? "");
    const b = plans.get(u.searchParams.get("b") ?? "");
    if (!a || !b) return notFound("Plan");
    return json<S["PlanComparison"]>({ a, b, metrics: {}, ops_a_to_b: [] });
  }),
  http.get(`${A}/plans/:id`, ({ params }) => {
    const p = plans.get(dec(params.id));
    return p ? json<S["PlanOut"]>(p) : notFound("Plan");
  }),
  http.patch(`${A}/plans/:id`, async ({ params, request }) => {
    const p = plans.get(dec(params.id));
    if (!p) return notFound("Plan");
    const body = (await request.json()) as S["PlanUpdate"];
    const next = { ...p, name: body.name ?? p.name, is_primary: body.is_primary ?? p.is_primary, state: body.state ?? p.state };
    plans.set(p.id, next);
    return json<S["PlanOut"]>(next);
  }),
  http.delete(`${A}/plans/:id`, ({ params }) => {
    plans.delete(dec(params.id));
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(`${A}/plans/:id/duplicate`, ({ params }) => {
    const p = plans.get(dec(params.id));
    return p ? json<S["PlanOut"]>(makePlan({ name: `${p.name} (copy)`, is_primary: false, state: p.state }), 201) : notFound("Plan");
  }),
  http.patch(`${A}/plans/:id/items`, async ({ params, request }) => {
    const p = plans.get(dec(params.id));
    if (!p) return notFound("Plan");
    const body = (await request.json()) as S["ItemsPatch"];
    const next = { ...p, state: applyOps(p.state, body.ops) };
    plans.set(p.id, next);
    return json<S["PlanOut"]>(next);
  }),
  http.get(`${A}/plans/:id/changesets`, () => json<S["ChangeSet"][]>([])),
  http.post(`${A}/plans/:id/changesets/:cs/apply`, ({ params }) => {
    const p = plans.get(dec(params.id));
    return p ? json<S["PlanOut"]>(p) : notFound("Plan");
  }),
  http.post(`${A}/plans/:id/changesets/:cs/discard`, ({ params }) =>
    json<S["ChangeSet"]>({ id: dec(params.cs), plan_id: dec(params.id), origin: "chat", ops: [], base_plan_hash: "mock", status: "discarded", preview_report: null }),
  ),

  // Admin (prompt 09)
  http.get(`${A}/admin/review-items`, () => json<S["Page_ReviewItemOut_"]>({ items: [], total: 0, limit: 50, offset: 0 })),
  http.post(`${A}/admin/review-items/:id/decision`, () => notFound("Review item")),
  http.post(`${A}/admin/program-versions/:id/publish`, () => notFound("Program version")),
];

/** A predicate for the courses a node path accepts (mock eligibility). */
function findNode(root: S["ProgramDetail"]["rules"], programId: string, path: string): ((code: string) => boolean) | null {
  type N = S["ProgramDetail"]["rules"];
  const walk = (p: string, node: N): ((code: string) => boolean) | null => {
    if (node.kind === "bounded_parts") {
      for (const part of node.parts) if (`${p}/${part.id}` === path) return (c) => matches(c, part.from);
    }
    if (p === path) {
      if (node.kind === "select") return (c) => matches(c, node.from);
      if (node.kind === "slot") return (c) => node.any_of.includes(c);
      if (node.kind === "bounded_parts") return (c) => node.parts.some((part) => matches(c, part.from));
      return null;
    }
    if (node.kind === "group") {
      for (const [i, child] of node.children.entries()) {
        const hit = walk(`${p}/${child.id ?? i + 1}`, child);
        if (hit) return hit;
      }
    }
    return null;
  };
  return walk(programId, root);
}

export { MOCK_CATALOG_YEAR };
