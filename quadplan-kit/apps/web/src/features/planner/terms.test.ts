import { academicYear, catalogYearFor, compareTerms, isBefore, planTerms, resolveTermRef, termAt, termLabel, yearIndex } from "./terms";

// Mirrors packages/planner_core/tests for planner_core.terms.
describe("terms", () => {
  it("orders terms chronologically", () => {
    expect(isBefore("2026-AU", "2027-WI")).toBe(true);
    expect(isBefore("2027-SU", "2027-AU")).toBe(true);
    expect(["2027-SP", "2026-AU", "2027-WI"].sort(compareTerms)).toEqual(["2026-AU", "2027-WI", "2027-SP"]);
  });

  it("maps terms to academic years and plan years", () => {
    expect(academicYear("2027-WI")).toBe(2026);
    expect(academicYear("2026-AU")).toBe(2026);
    expect(yearIndex("2028-SP", "2026-AU")).toBe(2);
    expect(termAt("2026-AU", 1, "AU")).toBe("2026-AU");
    expect(termAt("2026-AU", 2, "WI")).toBe("2028-WI");
    expect(termAt("2027-WI", 1, "SU")).toBe("2027-SU");
  });

  it("resolves relative term refs", () => {
    expect(resolveTermRef("Y2-SP", "2026-AU")).toBe("2028-SP");
    expect(resolveTermRef("2030-AU", "2026-AU")).toBe("2030-AU");
    expect(() => resolveTermRef("Y2-XX", "2026-AU")).toThrow();
    expect(() => resolveTermRef("26-AU", "2026-AU")).toThrow();
  });

  it("labels and lists terms", () => {
    expect(termLabel("2027-WI")).toBe("Winter 2027");
    expect(planTerms("2026-AU", 1)).toEqual(["2026-AU", "2027-WI", "2027-SP", "2027-SU"]);
    expect(catalogYearFor(new Date(2026, 10, 12))).toBe("2026-27");
    expect(catalogYearFor(new Date(2027, 2, 1))).toBe("2026-27");
  });
});
