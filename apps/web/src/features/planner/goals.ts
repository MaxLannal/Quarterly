/**
 * Goal chips shared by onboarding, the Goals tab and the Generate popup. Each chip maps to a
 * typed goal (SPEC "Goal predicates"). Numeric defaults are user-preference defaults, not
 * catalog facts; they are editable and listed in docs/OPEN_QUESTIONS.md.
 */
import type { Goal } from "@/api/types";
import { termAt } from "./terms";

let seq = 0;
export function goalId(prefix: string): string {
  seq += 1;
  return `${prefix}-${Date.now().toString(36)}-${seq}`;
}

const base = { hard: false, weight: 1 } as const;

export interface CareerPreset {
  key: string;
  label: string;
  make: (entryTerm: string) => Goal[];
}

export const CAREER_PRESETS: CareerPreset[] = [
  { key: "protect_gpa", label: "Protect GPA", make: () => [{ ...base, type: "protect_gpa", id: goalId("protect-gpa"), scope: "career", term: null, strictness_threshold: null }] },
  { key: "challenge", label: "Challenge me", make: () => [{ ...base, type: "challenge", id: goalId("challenge"), scope: "career", term: null, min_index: 10 }] },
  {
    key: "one_very_hard",
    label: "At most one very hard course per quarter",
    make: () => [{ ...base, type: "difficulty_cap", id: goalId("difficulty"), scope: "career", term: null, max_very_hard: 1, max_index: null, very_hard_threshold: null }],
  },
  {
    key: "lighter_first_year",
    label: "Lighter first year",
    make: (entry) =>
      (["AU", "WI", "SP"] as const).map((q) => ({ ...base, type: "light_quarter", id: goalId("light"), scope: "term", term: termAt(entry, 1, q), max_courses: 3 }) satisfies Goal),
  },
  {
    key: "graduate_4",
    label: "Graduate in four years",
    make: (entry) => [{ ...base, type: "graduate_by", id: goalId("graduate"), scope: "career", term: null, by_term: termAt(entry, 4, "SP") }],
  },
];

export interface TermPreset {
  key: string;
  label: string;
  make: (term: string, opts: { studyAbroadProgram?: string }) => Goal | null;
}

export const TERM_PRESETS: TermPreset[] = [
  { key: "light_quarter", label: "Light quarter", make: (term) => ({ ...base, type: "light_quarter", id: goalId("light"), scope: "term", term, max_courses: 3 }) },
  { key: "max_4", label: "At most 4 courses", make: (term) => ({ ...base, type: "course_load", id: goalId("load"), scope: "term", term, max_courses: 4, min_courses: null }) },
  {
    key: "study_abroad",
    label: "Study abroad",
    make: (term, { studyAbroadProgram }) =>
      studyAbroadProgram
        ? { ...base, type: "study_abroad", id: goalId("abroad"), scope: "term", term, abroad_term: term, program_id: studyAbroadProgram }
        : null,
  },
];

/**
 * The study-abroad program a "Study abroad" chip refers to: the one already on the plan when
 * there is one (a student who added Paris means Paris), otherwise the first in the catalog.
 */
export function studyAbroadProgramFor(planProgramIds: readonly string[], catalog: readonly { id: string; type: string }[]): string | undefined {
  const blocks = catalog.filter((p) => p.type === "study_abroad_block");
  return blocks.find((p) => planProgramIds.includes(p.id))?.id ?? blocks[0]?.id;
}

export function interestGoal(tags: string[]): Goal {
  return { ...base, type: "interest", id: goalId("interest"), scope: "career", term: null, tags, min_share: null };
}
