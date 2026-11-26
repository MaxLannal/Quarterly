/**
 * MSW handlers for the student record (Issue #14/#16): `/profile/questions` (the question file,
 * copied to questions.json by `make api-client`), `/me/profile` (GET, PATCH: a partial update
 * like the server's; credits and taken courses replace the whole list, unknown programs and
 * courses are refused with 422), `/me/profile/export.md` (a small fake student.md), and
 * `/agents/interview` (the dashboard agent without a model: it walks the step-2 questions in
 * order; an option or a value it can read becomes a proposal for that field, "Skip" moves on,
 * anything else asks the same question again with `retry`). The routes went in issue #15. No
 * model involved; fake data only.
 */
import { http, HttpResponse, type HttpHandler } from "msw";
import type { components } from "@/api/schema";
import { findCourse, PROGRAMS } from "./data";
import questionFile from "./questions.json";

type S = components["schemas"];
type Question = S["Question"];
const A = "*/api";
const QUESTIONS = questionFile as unknown as S["QuestionSet"];

const SESSION_FLAG = "quarterly.mock.session";
function loggedIn(): boolean {
  try {
    return globalThis.sessionStorage?.getItem(SESSION_FLAG) === "1";
  } catch {
    return false;
  }
}
const unauthorized = () => HttpResponse.json({ detail: "Log in to continue." }, { status: 401 });
const unprocessable = (detail: string) => HttpResponse.json({ detail }, { status: 422 });
const today = () => new Date().toISOString().slice(0, 10);

function sse(events: unknown[]) {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream" } });
}

/** Programs the mock knows besides the catalog's fake ones. */
const PROGRAM_NAMES: Record<string, string> = { "test-bs": "Test Studies BS (fake)", "cmsc-bs": "Computer Science (BS)" };
const programName = (id: string) => PROGRAMS.find((p) => p.id === id)?.name ?? PROGRAM_NAMES[id];

function emptyProfile(): S["ProfileOut"] {
  return {
    username: "fake-user",
    email: "fake-user@example.invalid",
    member_since: "2099-01-01",
    class_year: null,
    expected_graduation_term: null,
    intended_programs: [],
    programs: [],
    entry_term: null,
    entry_year_level: null,
    credits: [],
    taken_courses: [],
    post_grad_plan: null,
    pace: null,
    wants_research: null,
    research_areas: [],
    interests: [],
    course_load: null,
    terms_away: null,
    class_formats: null,
    theory_vs_application: null,
    answered: [],
    completeness: 0,
    has_working_notes: false,
    interview: { covered: [], turns: [] },
    follows: { threads: [], courses: [] },
    updated_day: today(),
  };
}

// The record outlives a page reload in the same tab, like the mock session (sessionStorage).
const PROFILE_FLAG = "quarterly.mock.profile";
function loadProfile(): S["ProfileOut"] {
  try {
    const raw = globalThis.sessionStorage?.getItem(PROFILE_FLAG);
    return raw ? { ...emptyProfile(), ...(JSON.parse(raw) as S["ProfileOut"]) } : emptyProfile();
  } catch {
    return emptyProfile();
  }
}
function storeProfile() {
  try {
    globalThis.sessionStorage?.setItem(PROFILE_FLAG, JSON.stringify(profile));
  } catch {
    // Storage blocked: the record lasts until the page reloads.
  }
}

let profile = loadProfile();
let workingNotes = "";

export function resetProfileMock() {
  profile = emptyProfile();
  try {
    globalThis.sessionStorage?.removeItem(PROFILE_FLAG);
  } catch {
    // Nothing stored.
  }
  workingNotes = "";
}

// ------------------------------------------------------------------------------ the record

const read = (p: S["ProfileOut"], field: string) => (p as unknown as Record<string, unknown>)[field];

function hasAnswer(q: Question, value: unknown): boolean {
  if (q.field === "terms_away" || q.field === "class_formats") return value !== null && value !== undefined;
  if (Array.isArray(value)) return value.length > 0;
  return value !== null && value !== undefined;
}

function applies(q: Question, p: S["ProfileOut"]): boolean {
  return Object.entries(q.when ?? {}).every(([name, wanted]) => name === "transfer_or_later" || Boolean(read(p, name)) === wanted);
}

function answeredIds(p: S["ProfileOut"]): string[] {
  return QUESTIONS.questions.filter((q) => hasAnswer(q, read(p, q.field))).map((q) => q.id);
}

function completeness(p: S["ProfileOut"]): number {
  const wanted = QUESTIONS.questions.filter((q) => !q.optional && !(q.when && "transfer_or_later" in q.when) && applies(q, p));
  if (!wanted.length) return 0;
  return Math.round((wanted.filter((q) => p.answered.includes(q.id)).length / wanted.length) * 1000) / 1000;
}

const TERM = /^\d{4}-(AU|WI|SP|SU)$/;

function applyPatch(patch: S["ProfilePatch"]): S["ProfileOut"] | { error: string } {
  const next: S["ProfileOut"] = { ...profile };
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined) continue;
    switch (key) {
      case "class_year":
        if (value !== null && (Number(value) < 2020 || Number(value) > 2040)) return { error: "class_year out of range" };
        next.class_year = value as number | null;
        break;
      case "entry_term":
      case "expected_graduation_term":
        if (value !== null && !TERM.test(String(value))) return { error: `${key} is not a quarter` };
        (next as Record<string, unknown>)[key] = value;
        break;
      case "intended_programs": {
        const ids = (value as string[] | null) ?? [];
        const unknown = ids.filter((id) => !programName(id));
        if (unknown.length) return { error: `Unknown program(s): ${unknown.join(", ")}` };
        next.intended_programs = ids;
        next.programs = ids.map((id) => ({ id, name: programName(id) ?? id }));
        break;
      }
      case "taken_courses": {
        const list = (value as S["TakenCourse"][] | null) ?? [];
        const unknown = list.filter((c) => !findCourse(c.course)).map((c) => c.course);
        if (unknown.length) return { error: `Unknown course(s): ${unknown.join(", ")}` };
        if (list.some((c) => !TERM.test(c.term))) return { error: "taken course term is not a quarter" };
        next.taken_courses = list.map((c) => ({ course: c.course, term: c.term, status: c.status ?? "completed", grade: c.status === "in_progress" ? null : (c.grade ?? null), grading: c.grading ?? "letter", units: c.units ?? null, locked: c.locked ?? false, title: findCourse(c.course)?.title ?? "" }));
        break;
      }
      case "credits":
        next.credits = ((value as S["RecordCredit"][] | null) ?? []).map((c) => ({ kind: c.kind, label: c.label, maps_to: c.maps_to ?? null, units: c.units ?? 0 }));
        break;
      case "research_areas":
      case "interests": {
        const seen = new Set<string>();
        const items: string[] = [];
        for (const raw of (value as string[] | null) ?? []) {
          const item = raw.replace(/\s+/g, " ").trim();
          if (item && !seen.has(item.toLowerCase())) {
            seen.add(item.toLowerCase());
            items.push(item);
          }
        }
        if (items.length > 24 || items.some((i) => i.length > 60)) return { error: "too many or too long" };
        next[key] = items;
        break;
      }
      case "interview": {
        const memory = value as S["InterviewMemoryPatch"] | null;
        next.interview = memory ? { covered: memory.covered ?? profile.interview.covered, turns: (memory.turns ?? profile.interview.turns).slice(-24) } : { covered: [], turns: [] };
        break;
      }
      case "working_notes":
        workingNotes = (value as string | null) ?? "";
        next.has_working_notes = !!workingNotes;
        break;
      default:
        (next as Record<string, unknown>)[key] = value ?? (Array.isArray(read(profile, key)) ? [] : null);
    }
  }
  next.answered = answeredIds(next);
  next.completeness = completeness(next);
  next.updated_day = today();
  return next;
}

/** A small fake student.md in the server's layout (groups as headings, "Not answered"). */
function studentMd(p: S["ProfileOut"]): string {
  const out = ["# Student record", "", "Fake export from the mock API.", "", "## General Information"];
  for (const group of QUESTIONS.groups) {
    out.push("", `### ${group.title}`, "");
    for (const q of QUESTIONS.questions.filter((x) => x.group === group.id)) {
      const value = read(p, q.field);
      out.push(`- ${q.label}: ${hasAnswer(q, value) ? JSON.stringify(value) : "Not answered"}`);
    }
  }
  return `${out.join("\n")}\n`;
}

// ------------------------------------------------------------------------------ the guide

const STEP2 = QUESTIONS.questions.filter((q) => q.step === 2);
const QUARTERS: Record<string, string> = { autumn: "AU", fall: "AU", winter: "WI", spring: "SP", summer: "SU" };

function quickReplies(q: Question): string[] {
  let replies = q.options.map((o) => o.label);
  if (q.type === "scale") replies = Array.from({ length: (q.max ?? 10) - (q.min ?? 1) + 1 }, (_, i) => String((q.min ?? 1) + i));
  if (q.id === "terms_away") replies = ["None"];
  return [...replies, "Skip"];
}

const fold = (s: string) => s.trim().toLowerCase();

function optionFor(q: Question, text: string): S["QuestionOption"] | undefined {
  const t = fold(text);
  return q.options.find((o) => fold(o.label) === t || fold(String(o.value)) === t);
}

/** The student's reply as the question's field value, or undefined when it does not map. */
function mapReply(q: Question, text: string): unknown {
  if (q.type === "scale") {
    const n = Number(/\d+/.exec(text)?.[0]);
    return n >= (q.min ?? 1) && n <= (q.max ?? 10) ? n : undefined;
  }
  if (q.type === "multi") {
    const parts = text.split(/\s*(?:,|\band\b)\s*/i).filter(Boolean);
    const values = parts.map((part) => optionFor(q, part)?.value);
    return values.length && values.every((v) => v !== undefined) ? q.options.map((o) => o.value).filter((v) => values.includes(v)) : undefined;
  }
  if (q.type === "list") {
    const items = text.split(/\s*,\s*/).map((s) => s.trim()).filter(Boolean);
    return items.length ? [...profile.research_areas, ...items.filter((i) => !profile.research_areas.some((r) => fold(r) === fold(i)))] : undefined;
  }
  if (q.id === "terms_away") {
    if (/^(none|no)\b/i.test(text.trim())) return [];
    const m = /(autumn|fall|winter|spring|summer)\s+(\d{4})/i.exec(text);
    if (!m) return undefined;
    const kind = /intern/i.test(text) ? "internship" : /leave/i.test(text) ? "leave" : "abroad";
    const term = `${m[2]}-${QUARTERS[(m[1] ?? "").toLowerCase()]}`;
    return [...(profile.terms_away ?? []).filter((t) => t.term !== term), { term, kind }];
  }
  const option = optionFor(q, text);
  if (option) return option.value;
  if (q.value === "boolean") return /^(yes|y|sure)\b/i.test(text) ? true : /^(no|n|nope)\b/i.test(text) ? false : undefined;
  if (q.value === "integer") {
    const n = Number(/\d+/.exec(text)?.[0]);
    return Number.isFinite(n) && n >= (q.min ?? 1) && n <= (q.max ?? 99) ? n : undefined;
  }
  return undefined;
}

function turn(q: Question | undefined, extra: Partial<S["InterviewTurnEvent"]>, progress: number) {
  if (!q) {
    return { type: "turn", text: "That's every question. Accept the answers that are right, and open the planner when you're ready.", topic: "wrapup", quick_replies: [], proposed: {}, answered: null, retry: false, progress: 1, done: true, courses: [], fallback: true, ...extra };
  }
  return { type: "turn", text: q.text, topic: q.id, quick_replies: quickReplies(q), proposed: {}, answered: null, retry: false, progress, done: false, courses: [], fallback: true, ...extra };
}

export function interviewReply(req: S["InterviewRequest"]): unknown[] {
  const history = req.history ?? [];
  const asked = [...history].reverse().find((t) => t.role === "guide")?.topic ?? null;
  // Covered: asked earlier and answered (a guide turn, a student turn, then another question;
  // the same question again was a retry). The last question is handled below.
  const covered = new Set(profile.interview.covered);
  let last: string | null = null;
  let replied = false;
  for (const t of history) {
    if (t.role === "guide") {
      if (last && replied && t.topic !== last) covered.add(last);
      last = t.topic ?? null;
      replied = false;
    } else replied = true;
  }
  if (req.mode === "welcome_back") {
    return [turn(STEP2.find((q) => !profile.answered.includes(q.id)), { text: "Welcome back. Shall we pick up where we left off?" }, profile.completeness), { type: "done", fallback: true, note: null }];
  }
  const question = STEP2.find((q) => q.id === asked);
  let proposed: S["ProfilePatch"] = {};
  let after = profile;
  if (req.mode === "reply" && question) {
    const text = req.message ?? "";
    if (fold(text) !== "skip") {
      const value = mapReply(question, text);
      if (value === undefined) {
        const progress = covered.size / STEP2.length;
        return [turn(question, { retry: true }, progress), { type: "done", fallback: true, note: null }];
      }
      proposed = { [question.field]: value } as S["ProfilePatch"];
      after = { ...profile, ...(proposed as Partial<S["ProfileOut"]>) };
    }
    covered.add(question.id);
  }
  const next = STEP2.find((q) => applies(q, after) && !covered.has(q.id) && !hasAnswer(q, read(after, q.field)) && q.id !== asked);
  const progress = Math.min(1, STEP2.filter((q) => covered.has(q.id) || hasAnswer(q, read(after, q.field))).length / STEP2.length);
  return [turn(next, { proposed, answered: Object.keys(proposed).length ? (question?.id ?? null) : null }, progress), { type: "done", fallback: true, note: null }];
}

export const profileHandlers: HttpHandler[] = [
  http.get(`${A}/profile/questions`, () => HttpResponse.json(QUESTIONS)),
  http.get(`${A}/me/profile`, () => (loggedIn() ? HttpResponse.json(profile) : unauthorized())),
  http.patch(`${A}/me/profile`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    const result = applyPatch((await request.json()) as S["ProfilePatch"]);
    if ("error" in result) return unprocessable(result.error);
    profile = result;
    storeProfile();
    return HttpResponse.json(profile);
  }),
  http.get(`${A}/me/profile/export.md`, () =>
    loggedIn()
      ? new HttpResponse(studentMd(profile), { headers: { "Content-Type": "text/markdown; charset=utf-8", "Content-Disposition": 'attachment; filename="student.md"' } })
      : unauthorized(),
  ),
  http.post(`${A}/agents/interview`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    return sse(interviewReply((await request.json()) as S["InterviewRequest"]));
  }),
];
