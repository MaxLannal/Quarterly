/**
 * MSW handlers for the campus companion's "profile" endpoints (docs/BEST-OF-UCHICAGO-PLAN.md):
 * `/me/profile` (GET, PATCH: a partial update like the server's) and `/agents/interview` (the
 * deterministic guide's topic order, streamed). The routes went in issue #15. No model involved;
 * fake data only.
 */
import { http, HttpResponse, type HttpHandler } from "msw";
import type { components } from "@/api/schema";

type S = components["schemas"];
const A = "*/api";

const SESSION_FLAG = "quarterly.mock.session";
function loggedIn(): boolean {
  try {
    return globalThis.sessionStorage?.getItem(SESSION_FLAG) === "1";
  } catch {
    return false;
  }
}
const unauthorized = () => HttpResponse.json({ detail: "Log in to continue." }, { status: 401 });
const today = () => new Date().toISOString().slice(0, 10);

function sse(events: unknown[]) {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream" } });
}

const PROGRAM_NAMES: Record<string, string> = { "test-bs": "Test Studies BS (fake)", "cmsc-bs": "Computer Science (BS)" };

function emptyProfile(): S["ProfileOut"] {
  return {
    username: "fake-user",
    email: "fake-user@example.invalid",
    member_since: "2099-01-01",
    class_year: null,
    intended_programs: [],
    programs: [],
    interests: [],
    research_areas: [],
    humanities_goal: null,
    humanities_topics: [],
    humanities_note: null,
    career_plans: null,
    career_paths: [],
    future_domains: [],
    constraints: [],
    workload: null,
    feed_categories: [],
    portrait: { headline: "", summary: "", themes: [] },
    interview: { covered: [], turns: [] },
    follows: { threads: [], courses: [] },
    completeness: 0,
    updated_day: today(),
  };
}

let profile = emptyProfile();

export function resetProfileMock() {
  profile = emptyProfile();
}

function completeness(p: S["ProfileOut"]): number {
  const filled = [
    p.class_year != null,
    p.interests.length > 0,
    p.research_areas.length > 0,
    p.humanities_goal != null || p.humanities_topics.length > 0,
    !!p.career_plans || p.career_paths.length > 0,
    p.future_domains.length > 0,
    p.constraints.length > 0 || p.workload != null,
  ];
  return Math.round((filled.filter(Boolean).length / filled.length) * 1000) / 1000;
}

function applyPatch(patch: S["ProfilePatch"]): S["ProfileOut"] | { error: string } {
  const next: S["ProfileOut"] = { ...profile };
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined) continue;
    if (key === "class_year" && value !== null && (Number(value) < 2020 || Number(value) > 2040)) return { error: "class_year out of range" };
    if (key === "intended_programs" && Array.isArray(value)) {
      const unknown = value.filter((v) => !(v in PROGRAM_NAMES));
      if (unknown.length) return { error: `Unknown program(s): ${unknown.join(", ")}` };
      next.intended_programs = value as string[];
      next.programs = (value as string[]).map((id) => ({ id, name: PROGRAM_NAMES[id] ?? id }));
      continue;
    }
    if (key === "interview") {
      const memory = value as S["InterviewMemoryPatch"] | null;
      next.interview = memory ? { covered: memory.covered ?? profile.interview.covered, turns: (memory.turns ?? profile.interview.turns).slice(-24) } : { covered: [], turns: [] };
      continue;
    }
    if (key === "portrait") {
      next.portrait = (value as S["Portrait"] | null) ?? { headline: "", summary: "", themes: [] };
      continue;
    }
    if (Array.isArray(value)) {
      const seen = new Set<string>();
      const items: string[] = [];
      for (const raw of value as string[]) {
        const item = raw.replace(/\s+/g, " ").trim();
        if (item && !seen.has(item.toLowerCase())) {
          seen.add(item.toLowerCase());
          items.push(item);
        }
      }
      if (items.length > 24 || items.some((i) => i.length > 60)) return { error: "too many or too long" };
      (next as Record<string, unknown>)[key] = items;
      continue;
    }
    (next as Record<string, unknown>)[key] = value ?? (Array.isArray((profile as Record<string, unknown>)[key]) ? [] : null);
  }
  next.completeness = completeness(next);
  next.updated_day = today();
  return next;
}

// ------------------------------------------------------------------------------ the guide

const TOPICS: S["InterviewTurnEvent"]["topic"][] = ["class_year", "interests", "humanities", "research", "career", "future", "constraints", "wrapup"];
const QUESTIONS: Record<string, [string, string[]]> = {
  class_year: ["Let's start simple: which class are you in?", ["Class of 2030", "Class of 2029", "Not sure yet"]],
  interests: ["What pulls at your attention?", ["Physics", "Film", "Philosophy"]],
  humanities: ["What do you want from Humanities in the Core: just to pass, a balance, to enjoy specific topics, or to go deep?", ["Just to pass", "A balance", "Enjoy specific topics", "Go deep"]],
  research: ["Is there a question you'd love to work on with a professor someday?", ["Not yet", "Machine learning"]],
  career: ["Where do you picture yourself after the College?", ["Research / PhD", "Tech", "Not sure yet"]],
  future: ["Which fields do you want to be heading toward in ten years?", ["Quantum computing", "Climate"]],
  constraints: ["How heavy do you want your quarters to feel?", ["Light", "Balanced", "Intense"]],
};

function facts(topic: string | null | undefined, text: string): S["ProfilePatch"] {
  if (!topic || /^not sure|^skip|^no/i.test(text)) return {};
  const items = text.split(/\s*(?:,|\band\b)\s*/i).map((s) => s.trim()).filter(Boolean);
  const merged = (field: "interests" | "research_areas" | "future_domains" | "humanities_topics" | "constraints") => [...profile[field], ...items.filter((i) => !profile[field].includes(i))];
  if (topic === "class_year") {
    const m = /20\d\d/.exec(text);
    return m ? { class_year: Number(m[0]) } : {};
  }
  if (topic === "interests") return { interests: merged("interests") };
  if (topic === "humanities") {
    if (/pass/i.test(text)) return { humanities_goal: "pass" };
    if (/balance/i.test(text)) return { humanities_goal: "balance" };
    if (/deep/i.test(text)) return { humanities_goal: "deep" };
    if (/enjoy/i.test(text)) return { humanities_goal: "enjoy" };
    return { humanities_topics: merged("humanities_topics") };
  }
  if (topic === "research") return { research_areas: merged("research_areas") };
  if (topic === "career") return { career_plans: text };
  if (topic === "future") return { future_domains: merged("future_domains") };
  if (topic === "constraints") return /light|balanced|intense/i.test(text) ? { workload: text.toLowerCase().match(/light|balanced|intense/)?.[0] as "light" } : { constraints: merged("constraints") };
  return {};
}

export function interviewReply(req: S["InterviewRequest"]): unknown[] {
  const steps = [
    { type: "step", tool: "search_courses", label: "Searching the catalog for “intro”", status: "started" },
    { type: "step", tool: "search_courses", label: "Searching the catalog for “intro”", status: "done" },
  ];
  const asked = [...(req.history ?? [])].reverse().find((t) => t.role === "guide")?.topic ?? null;
  const answered = new Set((req.history ?? []).filter((t) => t.role === "guide" && t.topic).map((t) => t.topic as string));
  if (req.mode === "reply" && asked) answered.add(asked);
  if (req.mode === "welcome_back") {
    return [
      { type: "turn", text: `Welcome back. Last time you told me about ${profile.interests[0] ?? "your plans"}. Want to keep going?`, quick_replies: ["Keep going", "Update my interests"], topic: "research", proposed: {}, progress: 0.3, done: false, courses: [], fallback: false },
      { type: "done", fallback: false, note: null },
    ];
  }
  const proposed = req.mode === "reply" ? facts(asked, req.message ?? "") : {};
  const next = TOPICS.find((t) => t !== "wrapup" && !answered.has(t)) ?? "wrapup";
  const progress = Math.min(1, answered.size / 7);
  if (next === "wrapup") {
    return [
      ...steps,
      {
        type: "turn",
        text: "That's everything I wanted to ask. Here's your portrait: “A fake student with real curiosity.”",
        quick_replies: ["Change something"],
        topic: "wrapup",
        proposed: { ...proposed, portrait: { headline: "A fake student with real curiosity", summary: "You like fake things.", themes: ["Testing"] } },
        progress: 1,
        done: true,
        courses: [],
        fallback: false,
      },
      { type: "done", fallback: false, note: null },
    ];
  }
  const [text, chips] = QUESTIONS[next] ?? ["Tell me more.", []];
  return [
    ...steps,
    { type: "turn", text, quick_replies: chips, topic: next, proposed, progress, done: false, courses: next === "interests" ? [{ code: "TEST 10000", title: "Fake Intro I" }] : [], fallback: false },
    { type: "done", fallback: false, note: null },
  ];
}

export const profileHandlers: HttpHandler[] = [
  http.get(`${A}/me/profile`, () => (loggedIn() ? HttpResponse.json(profile) : unauthorized())),
  http.patch(`${A}/me/profile`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    const result = applyPatch((await request.json()) as S["ProfilePatch"]);
    if ("error" in result) return HttpResponse.json({ detail: result.error }, { status: 422 });
    profile = result;
    return HttpResponse.json(profile);
  }),
  http.post(`${A}/agents/interview`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    return sse(interviewReply((await request.json()) as S["InterviewRequest"]));
  }),
];
