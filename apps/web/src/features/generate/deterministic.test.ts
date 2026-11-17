import { currentTerm, toOptions } from "./deterministic";

const form = {
  scope: "remaining" as const,
  selectedTerms: ["2027-WI"],
  load: -0.5,
  perTermLoad: { "2027-SP": 1 },
  maxCourses: 4,
  allowOverload: false,
  goals: [],
  interests: ["ML"],
  variants: 3,
};

describe("deterministic generator options", () => {
  it("maps dates to the quarter they fall in", () => {
    expect(currentTerm(new Date(2026, 10, 14))).toBe("2026-AU");
    expect(currentTerm(new Date(2027, 1, 1))).toBe("2027-WI");
    expect(currentTerm(new Date(2027, 4, 1))).toBe("2027-SP");
    expect(currentTerm(new Date(2027, 6, 1))).toBe("2027-AU");
  });

  it("sends today's quarter only for 'remaining quarters' and terms only for 'selected'", () => {
    const remaining = toOptions(form, "2027-WI");
    expect(remaining.today_term).toBe("2027-WI");
    expect(remaining.selected_terms).toEqual([]);
    expect(remaining.max_courses_per_term).toBe(4);
    const selected = toOptions({ ...form, scope: "selected" }, "2027-WI");
    expect(selected.today_term).toBeNull();
    expect(selected.selected_terms).toEqual(["2027-WI"]);
  });
});
