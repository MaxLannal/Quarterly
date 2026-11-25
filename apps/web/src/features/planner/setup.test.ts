import { describe, expect, it } from "vitest";
import type { PlanState } from "@/api/types";
import { testProfile } from "@/features/profile/fixtures";
import { buildPlanState, missingForPlan, planFromRecord, planToSave, recordKey, withRecord, type PlanDraft } from "./setup";

describe("a starting plan from the student record", () => {
  it("asks for a first quarter and programs first", () => {
    expect(missingForPlan(testProfile())).toEqual(["entry_term", "intended_programs"]);
    expect(missingForPlan(testProfile({ entry_term: "2026-AU", intended_programs: ["cs"] }))).toEqual([]);
  });

  it("takes the first quarter, year, graduation, programs plus the Core, credits and taken courses", () => {
    const state = planFromRecord(
      testProfile({
        entry_term: "2025-AU",
        entry_year_level: 2,
        expected_graduation_term: "2028-SP",
        intended_programs: ["cs"],
        credits: [{ kind: "transfer", label: "Calculus", maps_to: "MATH 15100", units: 100 }],
        taken_courses: [
          { course: "CMSC 14100", term: "2025-AU", status: "completed", grade: "A", grading: "letter", locked: false, title: "" },
          { course: "CMSC 14200", term: "2026-WI", status: "in_progress", grade: null, grading: "letter", locked: false, title: "" },
          { course: "OLD 10000", term: "2024-AU", status: "completed", grade: null, grading: "letter", locked: false, title: "" },
        ],
      }),
      "2026-27",
      ["core"],
    );
    expect(state.catalog_year).toBe("2026-27");
    expect(state.entry_term).toBe("2025-AU");
    expect(state.entry_year_level).toBe(2);
    expect(state.graduation_term).toBe("2028-SP");
    expect(state.programs?.map((p) => p.program_id)).toEqual(["cs", "core"]);
    expect(state.credits).toEqual([{ kind: "transfer", label: "Calculus", maps_to: "MATH 15100", units: 100 }]);
    expect(state.items?.map((i) => [i.course, i.term, i.status, i.grade])).toEqual([
      ["CMSC 14100", "2025-AU", "completed", "A"],
      ["CMSC 14200", "2026-WI", "in_progress", null],
    ]);
    expect(state.goals).toEqual([]);
  });

  it("keeps the wizard's rule: an undecided student keeps only the Core", () => {
    const draft: PlanDraft = { catalogYear: "2026-27", entryTerm: "2026-AU", yearLevel: 1, credits: [], programs: ["cs", "core"], undecided: true, interests: [], careerKeys: [], termGoals: [], generate: true };
    expect(buildPlanState(draft, undefined, ["core"]).programs?.map((p) => p.program_id)).toEqual(["core"]);
  });
});

describe("the student record inside a plan", () => {
  const base = planFromRecord(testProfile({ entry_term: "2026-AU", intended_programs: [] }), "2026-27");
  const plan = {
    ...base,
    credits: [{ kind: "AP" as const, label: "Old credit", maps_to: null, units: 100 }],
    items: [
      { id: "a", course: "PHYS 13100", term: "2026-AU", status: "completed" as const, grading: "letter" as const, locked: false, grade: "B" },
      { id: "b", course: "PHYS 13200", term: "2027-WI", status: "planned" as const, grading: "letter" as const, locked: false, grade: null },
    ],
  };
  const record = {
    credits: [{ kind: "transfer" as const, label: "New credit", maps_to: null, units: 100 }],
    taken_courses: [
      { course: "PHYS 13100", title: "Mechanics", term: "2026-AU", status: "completed" as const, grade: "A", grading: "letter" as const, locked: false },
      { course: "MATH 15100", title: "Calculus I", term: "2025-AU", status: "completed" as const, grade: null, grading: "letter" as const, locked: false },
    ],
  };

  it("replaces credits and taken courses with the record's, keeping planned items and ids", () => {
    const next = withRecord(plan, record);
    expect(next.credits).toEqual(record.credits);
    expect(next.items?.find((i) => i.id === "b")?.status).toBe("planned");
    const taken = next.items?.filter((i) => i.status === "completed") ?? [];
    // Same course and quarter keeps its id; a course before the first quarter is left out.
    expect(taken.map((i) => [i.id, i.course, i.grade])).toEqual([["a", "PHYS 13100", "A"]]);
  });

  it("compares the record part whatever the ids or order", () => {
    const shuffled = { ...plan, items: [...(plan.items ?? [])].reverse().map((i) => ({ ...i, id: `x${i.id}` })) };
    expect(recordKey(shuffled)).toBe(recordKey(plan));
    expect(recordKey(withRecord(plan, record))).not.toBe(recordKey(plan));
  });
});

// Blocker 2 (review of PR #21): the planner rebuilt every taken course as a letter-graded,
// unlocked course with the catalog's units, and Save wrote that back to the record. A Pass/Fail
// course could then count toward a rule that needs a letter grade.
describe("a taken course keeps its grading, units and lock", () => {
  const passFail = { course: "PHYS 13100", title: "Mechanics", term: "2026-AU", status: "completed" as const, grade: null, grading: "pass_fail" as const, units: 50, locked: true };
  const record = { credits: [], taken_courses: [passFail] };
  const kept = (state: PlanState) => state.items?.filter((i) => i.course === "PHYS 13100").map((i) => [i.grading, i.units, i.locked]);
  const opened = (base: PlanState = planFromRecord(testProfile({ entry_term: "2026-AU" }), "2026-27")) => withRecord(base, record);

  it("when the planner opens a plan and when it sets one up from the record", () => {
    expect(kept(opened())).toEqual([["pass_fail", 50, true]]);
    expect(kept(planFromRecord(testProfile({ entry_term: "2026-AU", taken_courses: [passFail] }), "2026-27"))).toEqual([["pass_fail", 50, true]]);
  });

  it("when Save sends the record's courses (the student did not change them here)", () => {
    const plan = opened();
    expect(kept(planToSave(plan, record, recordKey(plan)))).toEqual([["pass_fail", 50, true]]);
    expect(kept(planToSave(plan, record, null))).toEqual([["pass_fail", 50, true]]);
  });

  it("when the student unlocks or changes a taken course in the planner and saves", () => {
    const plan = opened();
    const base = recordKey(plan);
    const edited = { ...plan, items: plan.items?.map((i) => (i.course === "PHYS 13100" ? { ...i, locked: false, grading: "letter" as const, units: null } : i)) };
    expect(recordKey(edited)).not.toBe(base);
    expect(kept(planToSave(edited, record, base))).toEqual([["letter", null, false]]);
  });
});

