/**
 * Pure helpers of the dashboard (tested in logic.test.ts): the dashboard agent's answers that
 * wait for Accept, its memory, a question as a turn, the primary plan's summary, the route ->
 * local plan conversion for "Open in planner" (routes are removed on another branch), and small
 * formatters.
 */
import type { NodeProgress, PlanItem, PlanState } from "@/api/types";
import { emptyPlan } from "@/features/planner/planModel";
import { compareTerms, graduationTerm, planTerms, termAt } from "@/features/planner/terms";
import { answerText, questionById, type Question, type QuestionSet } from "@/features/profile/questions";
import { patched, type InterviewTurn, type Profile, type ProfilePatch, type Route, type RouteCourse, type TurnEvent } from "./api";

export const CAMPUS_YEAR = "2026-27";
export const MAX_ITEMS = 24;
export const MAX_ITEM_CHARS = 60;
export const MAX_TURNS = 24;
/** The quick reply that passes a question (the server adds it to every question). */
export const SKIP = "Skip";

const fold = (s: string) => s.trim().toLocaleLowerCase();

export function hasItem(items: readonly string[], item: string): boolean {
  return items.some((i) => fold(i) === fold(item));
}

/** `items` plus `item` (if new, and while there is room). */
export function withItem(items: readonly string[], item: string): string[] {
  const clean = item.replace(/\s+/g, " ").trim().slice(0, MAX_ITEM_CHARS);
  if (!clean || hasItem(items, clean) || items.length >= MAX_ITEMS) return [...items];
  return [...items, clean];
}

export function withoutItem(items: readonly string[], item: string): string[] {
  return items.filter((i) => fold(i) !== fold(item));
}

// ------------------------------------------------------------------------- the dashboard agent

/** An answer the dashboard agent mapped to a field, waiting for the student's Accept. */
export interface Proposal {
  /** The question it answers (the field names for an answer the question file does not know). */
  id: string;
  label: string;
  value: string;
  patch: ProfilePatch;
}

const sentFields = (patch: ProfilePatch | undefined) => Object.keys(patch ?? {}).filter((k) => patch?.[k as keyof ProfilePatch] !== undefined);
const read = (p: Profile, field: string) => (p as unknown as Record<string, unknown>)[field];

/**
 * The answer a turn proposes, as a card: the question it answers (`answered`, else the question
 * asked before it), that question's label, and how the answer reads once accepted. Null when the
 * turn proposes nothing, or only what the record already says.
 */
export function proposalFrom(turn: Pick<TurnEvent, "proposed" | "answered">, set: QuestionSet | undefined, profile: Profile, asked?: string | null): Proposal | null {
  const patch = turn.proposed ?? {};
  const fields = sentFields(patch).filter((f) => f !== "interview");
  if (!fields.length) return null;
  const after = patched(profile, patch);
  if (fields.every((f) => JSON.stringify(read(after, f)) === JSON.stringify(read(profile, f)))) return null;
  const question = questionById(set, turn.answered ?? asked) ?? set?.questions.find((q) => fields.includes(q.field));
  if (!question) return { id: fields.join(","), label: fields.join(", "), value: fields.map((f) => JSON.stringify(read(after, f))).join("; "), patch };
  return { id: question.id, label: question.label, value: answerText(question, after, set) ?? "Not answered", patch };
}

/** The quick replies of a question as the server sends them: its option labels unchanged (1 to
 * 10 for a scale, "None" for the quarters away), then "Skip". */
export function quickRepliesFor(question: Pick<Question, "id" | "type" | "options" | "min" | "max">): string[] {
  let replies = question.options.map((o) => o.label);
  if (question.type === "scale") {
    const min = question.min ?? 1;
    replies = Array.from({ length: (question.max ?? 10) - min + 1 }, (_, i) => String(min + i));
  }
  if (question.id === "terms_away") replies = ["None"];
  return [...replies, SKIP];
}

/** A question of the file as a guide turn: the dashboard opens the guide on it at once, without
 * asking the server first (the server reads the asked question from the history's `topic`). */
export function questionTurn(question: Question, progress = 0): TurnEvent {
  return {
    type: "turn",
    text: question.text,
    topic: question.id,
    quick_replies: quickRepliesFor(question),
    proposed: {},
    answered: null,
    retry: false,
    progress,
    done: false,
    courses: [],
    fallback: false,
  };
}

/** Several chips of a multi-choice question, sent as one answer in the options' order. */
export function multiReply(selected: readonly string[], order: readonly string[]): string {
  return order.filter((o) => selected.includes(o)).join(", ");
}

/** A reply that skips the question (the "Skip" button, or the word typed alone). */
const SKIP_REPLY = /^\s*skip\s*[.!]?\s*$/i;

/**
 * Topics this conversation moved past (a guide question, a reply, then a different question),
 * for the guide's progress chips only. A retried question does not count. Not saved: see
 * `skippedTopics`.
 */
export function discussedTopics(turns: readonly InterviewTurn[]): string[] {
  const out: string[] = [];
  let asked: string | null = null;
  let replied = false;
  const close = (next: string | null) => {
    if (asked && replied && next !== asked && !out.includes(asked)) out.push(asked);
  };
  for (const t of turns) {
    if (t.role === "guide") {
      close(t.topic ?? null);
      asked = t.topic ?? null;
      replied = false;
    } else if (asked) replied = true;
  }
  close(null);
  return out;
}

/**
 * Topics the student skipped in this conversation, in order: a guide question followed by a
 * "Skip" reply. Only skipped and accepted questions count as covered (Issue #16 step 22): an
 * answer the student never accepted leaves its question open, so the guide asks it again.
 */
export function skippedTopics(turns: readonly InterviewTurn[]): string[] {
  const out: string[] = [];
  let asked: string | null = null;
  for (const t of turns) {
    if (t.role === "guide") asked = t.topic ?? null;
    else if (asked && SKIP_REPLY.test(t.text) && !out.includes(asked)) out.push(asked);
  }
  return out;
}

/** The guide's memory to save: the last turns, and every question skipped or accepted so far. */
export function memoryPatch(profile: Profile, turns: readonly InterviewTurn[], accepted: readonly string[] = []): ProfilePatch {
  const covered = [...profile.interview.covered];
  for (const t of [...skippedTopics(turns), ...accepted]) if (!covered.includes(t)) covered.push(t);
  return {
    interview: {
      covered,
      turns: turns.slice(-MAX_TURNS).map((t) => ({ role: t.role, text: t.text.slice(0, 2000), topic: t.topic ?? null })),
    },
  };
}

// ------------------------------------------------------------------------------ the plan

export interface PlanSummary {
  entry: string;
  graduation: string;
  /** Each plan year: its quarters (Summer only when it holds a course) and their courses. */
  years: { year: number; terms: { term: string; courses: string[] }[] }[];
  courses: number;
}

/** The primary plan, read-only, year by year (D3: the plan changes only on the planner). */
export function planSummary(plan: Pick<PlanState, "entry_term" | "entry_year_level" | "graduation_term" | "items">): PlanSummary {
  const graduation = graduationTerm(plan);
  const items = plan.items ?? [];
  const terms = planTerms(plan.entry_term, graduation);
  const byTerm = new Map<string, string[]>();
  for (const item of items) {
    const code = item.course ?? item.slot_ref;
    if (!code) continue;
    byTerm.set(item.term, [...(byTerm.get(item.term) ?? []), code]);
  }
  const years: PlanSummary["years"] = [];
  terms.forEach((term, i) => {
    const year = Math.floor(i / 4) + 1;
    if (term.endsWith("-SU") && !byTerm.has(term)) return;
    let entry = years.find((y) => y.year === year);
    if (!entry) years.push((entry = { year, terms: [] }));
    entry.terms.push({ term, courses: byTerm.get(term) ?? [] });
  });
  for (const y of years) y.terms.sort((a, b) => compareTerms(a.term, b.term));
  return { entry: plan.entry_term, graduation, years, courses: items.filter((i) => i.course).length };
}

/** A program's progress on the plan: its top requirement node (the node id is the program id). */
export function programProgress(progress: readonly NodeProgress[] | undefined, programId: string): NodeProgress | undefined {
  return progress?.find((p) => p.program_id === programId && p.node_id === programId);
}

// ------------------------------------------------------------------------------ formatting

/** "today", "yesterday", "3 days ago", "in November 2026" (day-level dates only). */
export function memberSince(day: string, now: Date = new Date()): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  const then = Date.UTC(y, m - 1, d);
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((today - then) / 86_400_000);
  if (days <= 0) return "joined today";
  if (days === 1) return "joined yesterday";
  if (days < 14) return `joined ${days} days ago`;
  const month = new Date(then).toLocaleString("en-US", { month: "long", timeZone: "UTC" });
  return `member since ${month} ${y}`;
}

/** A small deterministic random generator. */
export function seeded(seed: number): () => number {
  let s = seed || 1;
  return () => {
    s = (Math.imul(s ^ (s >>> 15), 2246822519) + 0x9e3779b9) >>> 0;
    s ^= s >>> 13;
    return (s >>> 0) / 4294967296;
  };
}

// ------------------------------------------------------------------------------ routes

export const ROLE_LABELS: Record<RouteCourse["role"], string> = {
  major: "Major",
  minor: "Minor",
  core: "Core",
  humanities: "Humanities",
  research: "Research",
  elective: "Elective",
};
export const KIND_LABELS: Record<Route["kind"], string> = {
  major: "Major",
  double_major: "Double major",
  major_minor: "Major + minor",
  exploratory: "Exploratory",
  custom: "Custom",
};

/** The entering Autumn for a class year (class of 2030 entered in Autumn 2026). */
export function entryTermFor(classYear: number | null | undefined): string {
  const start = Number(CAMPUS_YEAR.slice(0, 4));
  if (!classYear) return `${start}-AU`;
  return `${classYear - 4}-AU`;
}

/**
 * A local plan state from a route: the catalog year Quarterly holds, the entry term from the
 * class year, the route's programs, and each course in its year and quarter (a course without
 * a quarter goes to the lightest of that year's quarters it is usually offered in). Returns the
 * state and the courses that could not be placed.
 */
export function routePlanState(route: Pick<Route, "courses" | "program_ids">, classYear: number | null | undefined): { state: PlanState; skipped: string[] } {
  const entry = entryTermFor(classYear);
  const state = emptyPlan(CAMPUS_YEAR, entry);
  const items: PlanItem[] = [];
  const skipped: string[] = [];
  const load = new Map<string, number>();
  const sorted = [...route.courses].sort((a, b) => a.year - b.year || (a.quarter ? 0 : 1) - (b.quarter ? 0 : 1));
  for (const course of sorted) {
    let term: string;
    try {
      if (course.quarter === "SU") {
        if (course.year >= 4) {
          skipped.push(course.code);
          continue;
        }
        term = termAt(entry, course.year + 1, "SU");
      } else if (course.quarter) {
        term = termAt(entry, course.year, course.quarter);
      } else {
        // The lightest of the quarters it is usually offered in (any of the three if unknown).
        const usual = (course.offered ?? []).filter((q): q is "AU" | "WI" | "SP" => q !== "SU");
        const options = (usual.length ? usual : (["AU", "WI", "SP"] as const)).map((q) => termAt(entry, course.year, q));
        term = options.reduce((best, t) => ((load.get(t) ?? 0) < (load.get(best) ?? 0) ? t : best), options[0] as string);
      }
    } catch {
      skipped.push(course.code);
      continue;
    }
    if (items.some((i) => i.course === course.code)) continue;
    load.set(term, (load.get(term) ?? 0) + 1);
    items.push({ course: course.code, term, status: "planned", grading: "letter", locked: false });
  }
  return {
    state: { ...state, items, programs: route.program_ids.map((program_id) => ({ program_id, options: {}, version_id: null })) },
    skipped,
  };
}

/** Courses of a route grouped by year, then quarter (null last). */
export function byYear(courses: readonly RouteCourse[]): Map<number, RouteCourse[]> {
  const order: Record<string, number> = { AU: 0, WI: 1, SP: 2, SU: 3 };
  const out = new Map<number, RouteCourse[]>([[1, []], [2, []], [3, []], [4, []]]);
  for (const c of courses) out.get(Math.min(4, Math.max(1, c.year)))?.push(c);
  for (const list of out.values()) list.sort((a, b) => (order[a.quarter ?? ""] ?? 9) - (order[b.quarter ?? ""] ?? 9));
  return out;
}

export const courseHref = (code: string) => `/courses/${encodeURIComponent(code)}`;
export const programHref = (id: string) => `/programs/${encodeURIComponent(id)}`;
