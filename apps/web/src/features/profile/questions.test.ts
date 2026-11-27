import { describe, expect, it } from "vitest";
import { aboutPatch, aboutProblem, EMPTY_ABOUT } from "./AboutYouForm";
import { TEST_QUESTIONS as SET, testProfile as profile, testQuestion as question } from "./fixtures";
import { answerText, applies, completenessOf, firstYearEntry, graduationFor, hasAnswer, remainingQuestions, termChoices } from "./questions";

describe("answers", () => {
  it("count an empty list as an answer only for quarters away and class formats", () => {
    expect(hasAnswer(profile({ terms_away: [] }), question("terms_away"))).toBe(true);
    expect(hasAnswer(profile({ terms_away: null }), question("terms_away"))).toBe(false);
    expect(hasAnswer(profile({ class_formats: [] }), question("class_formats"))).toBe(true);
    expect(hasAnswer(profile({ research_areas: [] }), question("research_areas"))).toBe(false);
    expect(hasAnswer(profile({ wants_research: false }), question("wants_research"))).toBe(true);
  });

  it("read with the question file's labels", () => {
    const p = profile({
      class_year: 2030,
      expected_graduation_term: "2030-SP",
      post_grad_plan: "grad_school",
      wants_research: true,
      course_load: "normal",
      terms_away: [{ term: "2028-AU", kind: "abroad" }],
      programs: [{ id: "cs", name: "Computer Science" }],
      intended_programs: ["cs"],
      credits: [{ kind: "AP", label: "Calculus", maps_to: null, units: 100 }],
    });
    expect(answerText(question("class_year"), p, SET)).toBe("Class of 2030");
    expect(answerText(question("expected_graduation_term"), p, SET)).toBe("Spring 2030");
    expect(answerText(question("post_grad_plan"), p, SET)).toBe("Graduate school");
    expect(answerText(question("wants_research"), p, SET)).toBe("Yes");
    expect(answerText(question("course_load"), p, SET)).toBe("Normal");
    expect(answerText(question("terms_away"), p, SET)).toBe("Autumn 2028 (Study abroad)");
    expect(answerText(question("intended_programs"), p, SET)).toBe("Computer Science");
    expect(answerText(question("credits"), p, SET)).toBe("1 credit");
    expect(answerText(question("pace"), p, SET)).toBeNull();
  });
});

describe("which questions apply", () => {
  it("asks for research areas only of a student interested in research", () => {
    expect(applies(question("research_areas"), profile({ wants_research: true }))).toBe(true);
    expect(applies(question("research_areas"), profile({ wants_research: false }))).toBe(false);
  });

  it("shows the transfer questions on the form only behind the checkbox, and credits to everyone", () => {
    expect(applies(question("taken_courses"), profile(), false)).toBe(false);
    expect(applies(question("taken_courses"), profile(), true)).toBe(true);
    expect(applies(question("taken_courses"), profile())).toBe(true);
    // Richard (2026-11-25): a first-year student can have AP, placement or transfer credits.
    expect(applies(question("credits"), profile(), false)).toBe(true);
    expect(question("credits").optional).toBe(true);
  });

  it("lists the agent's open questions and the share answered", () => {
    const p = profile({ post_grad_plan: "industry", wants_research: false, class_year: 2030 });
    const left = remainingQuestions(SET, p).map((q) => q.id);
    expect(left).toEqual(["pace", "interests", "course_load", "terms_away", "class_formats", "theory_vs_application"]);
    // Asked of this student: class year, graduation, programs + 8 step-2 questions (no research areas).
    expect(completenessOf(SET, p)).toBe(0.273);
  });
});

describe("quarters", () => {
  it("defaults the graduation to the Spring of the class year and a first-year to its Autumn", () => {
    expect(graduationFor(2030)).toBe("2030-SP");
    expect(firstYearEntry(2030)).toBe("2026-AU");
  });

  it("offers quarters around the class year, keeping a stored one", () => {
    const grad = termChoices("expected_graduation_term", 2030);
    expect(grad).toContain("2030-SP");
    expect(grad[0]).toBe("2028-WI");
    expect(termChoices("entry_term", 2030)).toContain("2026-AU");
    expect(termChoices("entry_term", 2030, "2015-AU")[0]).toBe("2015-AU");
  });
});

describe("the registration form", () => {
  it("needs a class year, and a first quarter and year for a transfer", () => {
    expect(aboutProblem(EMPTY_ABOUT, false)).toBe("Choose your class year.");
    expect(aboutProblem({ ...EMPTY_ABOUT, class_year: 2029 }, false)).toBeNull();
    expect(aboutProblem({ ...EMPTY_ABOUT, class_year: 2029 }, true)).toBe("Choose the quarter you started at UChicago.");
  });

  it("starts a first-year in the Autumn four years before the class year, with their credits", () => {
    const draft = {
      ...EMPTY_ABOUT,
      class_year: 2030,
      expected_graduation_term: "2030-SP",
      intended_programs: ["cs"],
      credits: [{ kind: "AP" as const, label: "x", maps_to: null, units: 100 }],
      taken_courses: [{ course: "MATH 15100", term: "2026-AU", status: "completed" as const, grading: "letter" as const, locked: false, title: "Calculus I" }],
    };
    expect(aboutPatch(draft, false)).toEqual({
      class_year: 2030,
      expected_graduation_term: "2030-SP",
      intended_programs: ["cs"],
      entry_term: "2026-AU",
      entry_year_level: 1,
      credits: [{ kind: "AP", label: "x", maps_to: null, units: 100 }],
      // Taken courses stay behind the checkbox: none are sent without it.
      taken_courses: [],
    });
  });

  it("sends a transfer student's first quarter, year, credits and taken courses", () => {
    const draft = {
      ...EMPTY_ABOUT,
      class_year: 2029,
      entry_term: "2026-AU",
      entry_year_level: 2,
      taken_courses: [{ course: "MATH 15100", term: "2026-AU", status: "completed" as const, grade: "A", grading: "pass_fail" as const, locked: true, title: "Calculus I" }],
    };
    expect(aboutPatch(draft, true)).toMatchObject({ entry_term: "2026-AU", entry_year_level: 2, credits: [], taken_courses: [{ course: "MATH 15100", term: "2026-AU", status: "completed", grade: "A", grading: "pass_fail", units: null, locked: true }] });
  });
});
