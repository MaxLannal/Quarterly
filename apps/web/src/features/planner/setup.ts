/**
 * A starting plan (moved here from the retired onboarding wizard, Issue #16): `buildPlanState`
 * is the wizard's own code; `planFromRecord` feeds it the student record instead of the
 * wizard's five steps (the registration form and the dashboard now collect the same answers),
 * and adds the expected graduation quarter and the taken courses as completed / in-progress
 * items. Tested in setup.test.ts.
 */
import type { Credit, Goal, PlanItem, PlanState } from "@/api/types";
import type { components } from "@/api/schema";
import { CAREER_PRESETS, interestGoal, TERM_PRESETS } from "./goals";
import { emptyPlan, newItemId } from "./planModel";
import { isBefore } from "./terms";

type Profile = components["schemas"]["ProfileOut"];

/** What the wizard collected (its `Draft`). */
export interface PlanDraft {
  catalogYear: string;
  entryTerm: string;
  yearLevel: number;
  credits: Credit[];
  programs: string[];
  undecided: boolean;
  interests: string[];
  careerKeys: string[];
  termGoals: { key: string; term: string }[];
  generate: boolean;
}

export function buildGoals(d: PlanDraft, abroad: string | undefined): Goal[] {
  const goals: Goal[] = [];
  for (const key of d.careerKeys) goals.push(...(CAREER_PRESETS.find((p) => p.key === key)?.make(d.entryTerm) ?? []));
  for (const g of d.termGoals) {
    const goal = TERM_PRESETS.find((p) => p.key === g.key)?.make(g.term, { studyAbroadProgram: abroad });
    if (goal) goals.push(goal);
  }
  if (d.interests.length) goals.push(interestGoal(d.interests));
  return goals;
}

/** Undecided students keep only the Core (programs of type "core"). */
export function buildPlanState(d: PlanDraft, abroad: string | undefined, coreIds: string[] = []): PlanState {
  return {
    ...emptyPlan(d.catalogYear, d.entryTerm),
    entry_year_level: d.yearLevel,
    credits: d.credits,
    programs: (d.undecided ? d.programs.filter((p) => coreIds.includes(p)) : d.programs).map((program_id) => ({ program_id, options: {}, version_id: null })),
    goals: buildGoals(d, abroad),
  };
}

/** What the record still needs before a plan can be set up from it (the questions' ids). */
export function missingForPlan(profile: Pick<Profile, "entry_term" | "intended_programs">): ("entry_term" | "intended_programs")[] {
  const out: ("entry_term" | "intended_programs")[] = [];
  if (!profile.entry_term) out.push("entry_term");
  if (!profile.intended_programs.length) out.push("intended_programs");
  return out;
}

/** The wizard's answers, read from the student record; the Core is always on the plan. */
export function draftFromRecord(profile: Profile, catalogYear: string, coreIds: string[] = []): PlanDraft {
  const programs = [...profile.intended_programs];
  for (const id of coreIds) if (!programs.includes(id)) programs.push(id);
  return {
    catalogYear,
    entryTerm: profile.entry_term ?? emptyPlan(catalogYear).entry_term,
    yearLevel: profile.entry_year_level ?? 1,
    credits: profile.credits as Credit[],
    programs,
    undecided: false,
    interests: [],
    careerKeys: [],
    termGoals: [],
    generate: true,
  };
}

/**
 * The starting plan from the record: the wizard's plan state, the expected graduation quarter
 * (when it comes after the first quarter), and each taken course in its quarter, completed or in
 * progress, with its grade. Courses before the first quarter are left out (the grid cannot show
 * them).
 */
export function planFromRecord(profile: Profile, catalogYear: string, coreIds: string[] = [], abroad?: string): PlanState {
  const draft = draftFromRecord(profile, catalogYear, coreIds);
  const state = buildPlanState(draft, abroad, coreIds);
  const graduation = profile.expected_graduation_term;
  const items: PlanItem[] = profile.taken_courses
    .filter((c) => !isBefore(c.term, state.entry_term))
    .map((c) => takenItem(c, newItemId()));
  return {
    ...state,
    ...(graduation && isBefore(state.entry_term, graduation) ? { graduation_term: graduation } : {}),
    items,
  };
}

// ---------------------------------------------------------------- the record inside a plan

/**
 * A taken course from the record as a plan item. Its grading, units and lock come from the
 * record too: a rule that needs a letter grade must not count a Pass/Fail course (Blocker 2,
 * review of PR #21).
 */
function takenItem(c: Profile["taken_courses"][number], id: string): PlanItem {
  return {
    id,
    course: c.course,
    term: c.term,
    status: c.status === "in_progress" ? "in_progress" : "completed",
    grading: c.grading ?? "letter",
    units: c.units ?? null,
    locked: c.locked ?? false,
    grade: c.grade ?? null,
  };
}

/** A taken course as a plan holds it: a completed or in-progress item with a course. */
function isTaken(item: PlanItem): boolean {
  return !!item.course && (item.status === "completed" || item.status === "in_progress");
}

/**
 * The student record's part of a plan (Issue #14): its credits and taken courses, in a form
 * that compares equal whatever the item ids or order. Used to tell whether the student changed
 * them in the planner since they were read from the record.
 */
export function recordKey(plan: PlanState): string {
  const credits = (plan.credits ?? []).map((c) => [c.kind, c.label, c.maps_to ?? null, c.units ?? 0]);
  const taken = (plan.items ?? [])
    .filter(isTaken)
    .map((i) => [i.course, i.term, i.status, i.grade ?? null, i.grading ?? "letter", i.units ?? null, i.locked ?? false])
    .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
  return JSON.stringify({ credits, taken });
}

/**
 * `plan` with its credits and taken courses replaced by the record's (taken courses before the
 * plan's first quarter are left out, as in `planFromRecord`). Planned items stay as they are.
 */
export function withRecord(plan: PlanState, profile: Pick<Profile, "credits" | "taken_courses">): PlanState {
  const kept = (plan.items ?? []).filter((i) => !isTaken(i));
  // Keep the ids of taken courses the plan already shows (change sets refer to item ids).
  const ids = new Map((plan.items ?? []).filter(isTaken).map((i) => [`${i.course} ${i.term}`, i.id]));
  const taken: PlanItem[] = profile.taken_courses
    .filter((c) => !isBefore(c.term, plan.entry_term))
    .map((c) => takenItem(c, ids.get(`${c.course} ${c.term}`) ?? newItemId()));
  return { ...plan, credits: profile.credits as Credit[], items: [...kept, ...taken] };
}

/**
 * What Save sends. Saving writes the plan's credits and taken courses to the record, so unless
 * the student changed them in the planner since `base` (their `recordKey` when last read from or
 * saved to the record; null = never read), Save sends the record's current ones: an old copy
 * never undoes a change made on the dashboard.
 */
export function planToSave(plan: PlanState, fresh: Pick<Profile, "credits" | "taken_courses">, base: string | null): PlanState {
  return base === null || recordKey(plan) === base ? withRecord(plan, fresh) : plan;
}
