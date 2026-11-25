import { describe, expect, it } from "vitest";
import { TEST_QUESTIONS as SET, testProfile as profile, testQuestion as question } from "@/features/profile/fixtures";
import { optimisticRoutes, patched, type Route, type RouteList } from "./api";
import { byYear, skippedTopics, entryTermFor, memberSince, memoryPatch, multiReply, planSummary, programProgress, proposalFrom, questionTurn, quickRepliesFor, routePlanState, withItem } from "./logic";

function route(over: Partial<Route> = {}): Route {
  return {
    id: "r1",
    title: "Physics first",
    tagline: "",
    summary: "",
    kind: "major",
    program_ids: ["phys-bs"],
    courses: [],
    milestones: [],
    fit: { interests: 0.5, career: 0.5, humanities: 0.5, workload: null },
    origin: "ai",
    status: "open",
    position: 0,
    note: null,
    created_day: "2026-11-20",
    updated_day: "2026-11-20",
    programs: [],
    ...over,
  };
}

describe("the dashboard agent's proposals", () => {
  it("names the question it answers and how the answer will read", () => {
    const p = proposalFrom({ proposed: { class_formats: ["seminar", "lab"] }, answered: "class_formats" }, SET, profile());
    expect(p).toEqual({ id: "class_formats", label: "Class formats", value: "Seminar, Lab", patch: { class_formats: ["seminar", "lab"] } });
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
    const before = profile({ taken_courses: [{ course: "MATH 15100", term: "2025-AU", status: "completed", grade: null, title: "Calculus I" }], programs: [{ id: "cs", name: "Computer Science" }], intended_programs: ["cs"] });
    const next = patched(before, { taken_courses: [{ course: "MATH 15100", term: "2025-AU", status: "completed", grade: "A" }], intended_programs: ["cs", "math"] });
    expect(next.taken_courses[0]).toMatchObject({ title: "Calculus I", grade: "A" });
    expect(next.programs).toEqual([{ id: "cs", name: "Computer Science" }, { id: "math", name: "math" }]);
  });

  it("choosing a route opens the one chosen before", () => {
    const list: RouteList = { items: [route({ id: "a", status: "chosen" }), route({ id: "b" })], chosen_id: "a", max_routes: 12 };
    const next = optimisticRoutes(list, "b", { status: "chosen" });
    expect(next.items.map((r) => r.status)).toEqual(["open", "chosen"]);
    expect(next.chosen_id).toBe("b");
    expect(optimisticRoutes(next, "b", { status: "open" }).chosen_id).toBeNull();
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

describe("open in planner", () => {
  it("places courses by year and quarter from the class year", () => {
    expect(entryTermFor(2029)).toBe("2025-AU");
    expect(entryTermFor(null)).toBe("2026-AU");
    const { state, skipped } = routePlanState(
      {
        program_ids: ["phys-bs"],
        courses: [
          { code: "PHYS 13100", title: "Mechanics", year: 1, quarter: "AU", role: "major", note: "", offered: [] },
          { code: "PHYS 13200", title: "E&M", year: 1, quarter: "WI", role: "major", note: "", offered: [] },
          { code: "HUMA 12050", title: "Greece", year: 1, quarter: null, role: "humanities", note: "", offered: [] },
          { code: "PHYS 23410", title: "QM", year: 3, quarter: "SP", role: "major", note: "", offered: [] },
          { code: "PHYS 29000", title: "Summer", year: 4, quarter: "SU", role: "research", note: "", offered: [] },
        ],
      },
      2030,
    );
    expect(state.entry_term).toBe("2026-AU");
    expect(state.catalog_year).toBe("2026-27");
    expect(state.items?.map((i) => [i.course, i.term])).toEqual([
      ["PHYS 13100", "2026-AU"],
      ["PHYS 13200", "2027-WI"],
      ["HUMA 12050", "2027-SP"],
      ["PHYS 23410", "2029-SP"],
    ]);
    expect(skipped).toEqual(["PHYS 29000"]);
    expect(state.programs?.[0]?.program_id).toBe("phys-bs");
  });

  it("puts a course without a quarter in a quarter it is usually offered in", () => {
    const { state } = routePlanState(
      {
        program_ids: [],
        courses: [
          { code: "A 10000", title: "", year: 1, quarter: "AU", role: "major", note: "", offered: ["AU"] },
          { code: "B 10000", title: "", year: 1, quarter: null, role: "major", note: "", offered: ["AU", "SP"] },
          { code: "C 10000", title: "", year: 1, quarter: null, role: "major", note: "", offered: ["AU", "SP"] },
        ],
      },
      2030,
    );
    expect(state.items?.map((i) => i.term)).toEqual(["2026-AU", "2027-SP", "2026-AU"]);
  });

  it("groups by year", () => {
    const years = byYear([
      { code: "B", title: "", year: 2, quarter: "SP", role: "elective", note: "", offered: [] },
      { code: "A", title: "", year: 2, quarter: "AU", role: "elective", note: "", offered: [] },
    ]);
    expect(years.get(2)?.map((c) => c.code)).toEqual(["A", "B"]);
    expect(years.get(1)).toEqual([]);
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
