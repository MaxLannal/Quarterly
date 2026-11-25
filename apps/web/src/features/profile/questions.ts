/**
 * The General Information questions (Issue #14, `data/profile/questions.yaml`, served by
 * `GET /profile/questions`) and the pure helpers around them (tested in questions.test.ts):
 * which questions apply to a student, whether one is answered, how an answer reads, and the
 * quarters a term question offers. Question text and options always come from the file; only
 * the record's field names are known here (they are the API contract).
 */
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { parseTerm, termKey, termLabel } from "@/features/planner/terms";

type S = components["schemas"];
export type QuestionSet = S["QuestionSet"];
export type Question = S["Question"];
export type QuestionOption = S["QuestionOption"];
export type Profile = S["ProfileOut"];
export type ProfilePatch = S["ProfilePatch"];
export type RecordCredit = S["RecordCredit"];
export type TakenCourse = S["TakenCourse"];
export type TakenCourseOut = S["TakenCourseOut"];
export type TermAway = S["TermAway"];

export const QUESTIONS_KEY = ["profile", "questions"] as const;

/** The question file never changes while the page is open. */
export function useQuestions() {
  return useQuery({
    queryKey: QUESTIONS_KEY,
    queryFn: async () => unwrap(await api.GET("/profile/questions")),
    staleTime: Infinity,
    retry: 1,
  });
}

/** Fields where an empty list is an answer ("none"); `null` means "not answered". */
const EMPTY_IS_ANSWER = new Set(["terms_away", "class_formats"]);

/** The stored value of a question's field. */
export function valueOf(profile: Profile, question: Pick<Question, "field">): unknown {
  return (profile as unknown as Record<string, unknown>)[question.field];
}

/** Whether a value counts as an answer (the server's `_has_answer`). */
export function isAnswer(question: Pick<Question, "field">, value: unknown): boolean {
  if (EMPTY_IS_ANSWER.has(question.field)) return value !== null && value !== undefined;
  if (Array.isArray(value)) return value.length > 0;
  return value !== null && value !== undefined;
}

export function hasAnswer(profile: Profile, question: Question): boolean {
  return isAnswer(question, valueOf(profile, question));
}

/**
 * Whether a question is asked of this student: its `when` fields have the given values.
 * `transfer_or_later` is the registration form's checkbox, not a stored field: the form passes
 * it in; the dashboard shows the transfer questions to everyone (every student has a first
 * quarter, and anyone may have credits).
 */
export function applies(question: Question, profile: Partial<Profile>, transferOrLater = true): boolean {
  for (const [name, wanted] of Object.entries(question.when ?? {})) {
    if (name === "transfer_or_later") {
      if (transferOrLater !== wanted) return false;
      continue;
    }
    if (Boolean((profile as Record<string, unknown>)[name]) !== wanted) return false;
  }
  return true;
}

const isTransferQuestion = (q: Question) => !!q.when && "transfer_or_later" in q.when;

/** The dashboard agent's questions (step 2) that apply and have no answer yet. */
export function remainingQuestions(set: QuestionSet | undefined, profile: Profile): Question[] {
  return (set?.questions ?? []).filter((q) => q.step === 2 && applies(q, profile) && !hasAnswer(profile, q));
}

/** Share of the questions that apply and are answered, the transfer-only ones left out (the
 * server's `completeness`, for optimistic updates before the server answers). */
export function completenessOf(set: QuestionSet | undefined, profile: Profile): number {
  const wanted = (set?.questions ?? []).filter((q) => !isTransferQuestion(q) && applies(q, profile));
  if (!wanted.length) return profile.completeness;
  return Math.round((wanted.filter((q) => hasAnswer(profile, q)).length / wanted.length) * 1000) / 1000;
}

export function questionsIn(set: QuestionSet | undefined, group: string): Question[] {
  return (set?.questions ?? []).filter((q) => q.group === group);
}

export function questionById(set: QuestionSet | undefined, id: string | null | undefined): Question | undefined {
  return id ? set?.questions.find((q) => q.id === id) : undefined;
}

/** The label of a table column's value ("in_progress" -> "In progress"). */
export function columnLabel(set: QuestionSet | undefined, column: string, value: string): string {
  return set?.labels?.[column]?.[value] ?? value;
}

/** The option whose value equals `value` (options carry booleans, integers or strings). */
export function optionFor(question: Question, value: unknown): QuestionOption | undefined {
  return question.options.find((o) => o.value === value);
}

/**
 * How an answer reads on the dashboard and in the guide ("Seminar, Lab", "Spring 2030",
 * "7 of 10 (1 = Theory, 10 = Application)"), or null when there is no answer.
 */
export function answerText(question: Question, profile: Profile, set?: QuestionSet): string | null {
  const value = valueOf(profile, question);
  if (!isAnswer(question, value)) return null;
  switch (question.field) {
    case "intended_programs": {
      const names = new Map(profile.programs.map((p) => [p.id, p.name]));
      return (value as string[]).map((id) => names.get(id) ?? id).join(", ");
    }
    case "credits": {
      const n = (value as RecordCredit[]).length;
      return `${n} credit${n === 1 ? "" : "s"}`;
    }
    case "taken_courses": {
      const n = (value as TakenCourseOut[]).length;
      return `${n} course${n === 1 ? "" : "s"}`;
    }
    case "terms_away": {
      const list = value as TermAway[];
      if (!list.length) return "None";
      return list.map((t) => `${termLabel(t.term)} (${columnLabel(set, "away", t.kind)})`).join(", ");
    }
    case "research_areas":
      return (value as string[]).join(", ");
    default:
      break;
  }
  if (Array.isArray(value)) {
    if (!value.length) return "None";
    return value.map((v) => optionFor(question, v)?.label ?? String(v)).join(", ");
  }
  if (question.value === "term" && typeof value === "string") return termLabel(value);
  if (question.type === "scale") {
    const ends = question.ends ? ` (${question.min ?? 1} = ${question.ends.min}, ${question.max ?? 10} = ${question.ends.max})` : "";
    return `${String(value)} of ${question.max ?? 10}${ends}`;
  }
  return optionFor(question, value)?.label ?? String(value);
}

/** The default expected graduation: the Spring of the class year. */
export function graduationFor(classYear: number): string {
  return `${classYear}-SP`;
}

/** A first-year's first quarter: the Autumn four years before the class year. */
export function firstYearEntry(classYear: number): string {
  return `${classYear - 4}-AU`;
}

const CALENDAR = ["WI", "SP", "SU", "AU"] as const;

/** Every quarter from the Winter of `from` to the Autumn of `to`, in order. */
export function termsBetween(from: number, to: number): string[] {
  const out: string[] = [];
  for (let y = from; y <= to; y++) for (const q of CALENDAR) out.push(`${y}-${q}`);
  return out;
}

/**
 * The quarters a term question offers: around the class year for the expected graduation, the
 * years before it for a first quarter, the college years for a quarter away. A stored value
 * outside the range stays in the list.
 */
export function termChoices(field: string, classYear: number | null | undefined, current?: string | null, now: Date = new Date()): string[] {
  const year = classYear ?? now.getFullYear() + 3;
  let terms: string[];
  if (field === "expected_graduation_term") terms = termsBetween(year - 2, year + 2);
  else if (field === "entry_term") terms = termsBetween(year - 7, year - 3);
  else terms = termsBetween(year - 4, year);
  if (current && !terms.includes(current)) {
    try {
      parseTerm(current);
      terms = [...terms, current].sort((a, b) => termKey(a) - termKey(b));
    } catch {
      // Not a term id: leave it out.
    }
  }
  return terms;
}
