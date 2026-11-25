import { describe, expect, it } from "vitest";
import { TEST_QUESTIONS as SET, testProfile as profile, testQuestion as question } from "@/features/profile/fixtures";
import { patched } from "./api";
import { skippedTopics, memberSince, memoryPatch, multiReply, planSummary, programProgress, proposalFrom, questionTurn, quickRepliesFor, withItem } from "./logic";

describe("the dashboard agent's proposals", () => {
  it("names the question it answers and how the answer will read", () => {
    const p = proposalFrom({ proposed: { class_formats: ["seminar", "lab"] }, answered: "class_formats" }, SET, profile());
    expect(p).toEqual({ id: "class_formats", label: "Class formats", value: "Seminar, Lab", patch: { class_formats: ["seminar", "lab"] } });
  });

  it("keeps only the answered field when a proposal also lists other fields as null", () => {
    // Richard's report (2026-11-25): the server sent every field of the patch, the unasked ones
    // as null, and Accept saved them all, which cleared every other answer.
    const proposed = { class_year: null, intended_programs: null, pace: "early", courses_per_term: null, terms_away: null } as const;
    const p = proposalFrom({ proposed, answered: "pace" }, SET, profile({ class_year: 2029, intended_programs: ["cs"] }));
    expect(p?.patch).toEqual({ pace: "early" });
    expect(p?.label).toBe("Graduation pace");
  });

  it("falls back to the question asked before when `answered` is missing", () => {
    const p = proposalFrom({ proposed: { theory_vs_application: 7 }, answered: null }, SET, profile(), "theory_vs_application");
    expect(p?.label).toBe("Theory or application");
    expect(p?.value).toBe("7 of 10 (1 = Theory, 10 = Application)");
  });

  it("offers nothing for an empty proposal or one the record already holds", () => {
    expect(proposalFrom({ proposed: {}, answered: null }, SET, profile())).toBeNull();
    expect(proposalFrom({ proposed: { pace: "early" }, answered: "pace" }, SET, profile({ pace: "early" }))).toBeNull();
  });

  it("reads 'None' for no quarters away", () => {
    expect(proposalFrom({ proposed: { terms_away: [] }, answered: "terms_away" }, SET, profile())?.value).toBe("None");
  });
});

describe("questions as turns", () => {
  it("sends the option labels unchanged, then Skip", () => {
    expect(quickRepliesFor(question("pace"))).toEqual(["Early", "On time", "Flexible", "Skip"]);
    expect(quickRepliesFor(question("theory_vs_application"))).toEqual(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Skip"]);
    expect(quickRepliesFor(question("terms_away"))).toEqual(["None", "Skip"]);
    const turn = questionTurn(question("courses_per_term"), 0.5);
    expect(turn).toMatchObject({ type: "turn", topic: "courses_per_term", text: question("courses_per_term").text, progress: 0.5, retry: false });
  });

  it("joins picked chips in the options' order", () => {
    expect(multiReply(["Lab", "Seminar"], ["Seminar", "Lecture", "Lab", "Online"])).toBe("Seminar, Lab");
  });
});

describe("the guide's memory", () => {
  it("keeps the last 24 turns and the questions skipped or accepted", () => {
    const turns = [
      { role: "guide" as const, text: "After graduation?", topic: "post_grad_plan" },
      { role: "student" as const, text: "Graduate school" },
      { role: "guide" as const, text: "How fast?", topic: "pace" },
      { role: "student" as const, text: "Skip" },
      { role: "guide" as const, text: "Research?", topic: "wants_research" },
    ];
    expect(skippedTopics(turns)).toEqual(["pace"]);
    const many = Array.from({ length: 30 }, (_, i) => ({ role: "student" as const, text: `t${i}` }));
    const patch = memoryPatch(profile({ interview: { covered: ["research_areas"], turns: [] } }), [...turns, ...many], ["post_grad_plan"]);
    expect(patch.interview?.covered).toEqual(["research_areas", "pace", "post_grad_plan"]);
    expect(patch.interview?.turns).toHaveLength(24);
  });

  it("leaves an answer the student did not accept open, so the guide asks again", () => {
    const turns = [
      { role: "guide" as const, text: "Formats?", topic: "class_formats" },
      { role: "student" as const, text: "Lab" },
      { role: "guide" as const, text: "Scale?", topic: "theory_vs_application" },
    ];
    expect(skippedTopics(turns)).toEqual([]);
    expect(memoryPatch(profile({ interview: { covered: [], turns: [] } }), turns).interview?.covered).toEqual([]);
  });

  it("dedupes list items case-insensitively", () => {
    expect(withItem(["Physics"], " physics ")).toEqual(["Physics"]);
    expect(withItem(["Physics"], "Film")).toEqual(["Physics", "Film"]);
  });
});

describe("patches", () => {
  it("apply like the server: only sent fields, null clears, answered follows", () => {
    const next = patched(profile({ class_year: 2029, answered: ["class_year"] }), { class_year: null, research_areas: ["Lasers"], terms_away: [] });
    expect(next.class_year).toBeNull();
    expect(next.research_areas).toEqual(["Lasers"]);
    expect(next.terms_away).toEqual([]);
    expect(next.answered.sort()).toEqual(["research_areas", "terms_away"]);
    expect(next.interview.covered).toEqual(["pace"]);
  });

  it("keeps known course titles and program names", () => {
    const before = profile({ taken_courses: [{ course: "MATH 15100", term: "2025-AU", status: "completed", grade: null, grading: "letter", locked: false, title: "Calculus I" }], programs: [{ id: "cs", name: "Computer Science" }], intended_programs: ["cs"] });
    const next = patched(before, { taken_courses: [{ course: "MATH 15100", term: "2025-AU", status: "completed", grade: "A", grading: "letter", locked: false }], intended_programs: ["cs", "math"] });
    expect(next.taken_courses[0]).toMatchObject({ title: "Calculus I", grade: "A" });
    expect(next.programs).toEqual([{ id: "cs", name: "Computer Science" }, { id: "math", name: "math" }]);
  });
});

describe("the plan summary", () => {
  it("lists each year's quarters with their courses, Summer only when used", () => {
    const summary = planSummary({
      entry_term: "2026-AU",
      entry_year_level: 1,
      graduation_term: null,
      items: [
        { course: "MATH 15100", term: "2026-AU", status: "planned", grading: "letter", locked: false },
        { course: "CMSC 14100", term: "2026-AU", status: "planned", grading: "letter", locked: false },
        { course: "PHYS 13100", term: "2028-SU", status: "planned", grading: "letter", locked: false },
      ],
    });
    expect(summary.graduation).toBe("2030-SP");
    expect(summary.courses).toBe(3);
    expect(summary.years).toHaveLength(4);
    expect(summary.years[0]?.terms.map((t) => t.term)).toEqual(["2026-AU", "2027-WI", "2027-SP"]);
    expect(summary.years[0]?.terms[0]?.courses).toEqual(["MATH 15100", "CMSC 14100"]);
    expect(summary.years[2]?.terms.map((t) => t.term)).toEqual(["2028-SU", "2028-AU", "2029-WI", "2029-SP"]);
  });

  it("finds a program's top requirement node", () => {
    const progress = [
      { program_id: "cs", node_id: "cs/intro", have: 1, need: 2, satisfied: false, unit: "courses" as const },
      { program_id: "cs", node_id: "cs", have: 3, need: 10, satisfied: false, unit: "courses" as const },
    ];
    expect(programProgress(progress, "cs")?.need).toBe(10);
    expect(programProgress(progress, "math")).toBeUndefined();
  });
});

describe("member since", () => {
  it("speaks in days, then months", () => {
    const now = new Date(2026, 10, 20);
    expect(memberSince("2026-11-20", now)).toBe("joined today");
    expect(memberSince("2026-11-17", now)).toBe("joined 3 days ago");
    expect(memberSince("2026-09-02", now)).toBe("member since September 2026");
  });
});
