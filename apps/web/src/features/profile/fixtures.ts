/** Test data for the student record (unit tests only; no real person). */
import questionFile from "@/mocks/questions.json";
import type { Profile, Question, QuestionSet } from "./questions";

export const TEST_QUESTIONS = questionFile as unknown as QuestionSet;

export function testQuestion(id: string): Question {
  const q = TEST_QUESTIONS.questions.find((x) => x.id === id);
  if (!q) throw new Error(`no question ${id}`);
  return q;
}

export function testProfile(over: Partial<Profile> = {}): Profile {
  return {
    username: "fake-user",
    email: "fake@example.invalid",
    member_since: "2026-11-01",
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
    courses_per_term: null,
    terms_away: null,
    class_formats: null,
    theory_vs_application: null,
    answered: [],
    completeness: 0,
    has_working_notes: false,
    feed_categories: [],
    interview: { covered: ["pace"], turns: [] },
    follows: { threads: [], courses: [] },
    updated_day: "2026-11-20",
    ...over,
  };
}
