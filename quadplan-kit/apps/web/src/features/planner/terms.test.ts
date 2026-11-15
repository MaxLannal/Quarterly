import {
  academicYear,
  academicYearLabel,
  catalogYearFor,
  classYearLabel,
  compareTerms,
  defaultGraduationTerm,
  graduationTerm,
  isBefore,
  planTerms,
  planYearCount,
  QUARTERS,
  resolveTermRef,
  termAt,
  termLabel,
  yearIndex,
} from "./terms";

// Mirrors packages/planner_core/tests for planner_core.terms (test_terms_and_years.py).
describe("terms", () => {
  it("orders terms chronologically", () => {
    expect(isBefore("2026-AU", "2027-WI")).toBe(true);
    expect(isBefore("2027-SU", "2027-AU")).toBe(true);
    expect(["2027-SP", "2026-AU", "2027-WI"].sort(compareTerms)).toEqual(["2026-AU", "2027-WI", "2027-SP"]);
  });

  it("opens each academic year with its Summer (FEEDBACK F2)", () => {
    expect(QUARTERS).toEqual(["SU", "AU", "WI", "SP"]);
    expect(academicYear("2026-SU")).toBe(2026);
    expect(academicYear("2026-AU")).toBe(2026);
    expect(academicYear("2027-WI")).toBe(2026);
    expect(academicYear("2027-SP")).toBe(2026);
    expect(academicYear("2027-SU")).toBe(2027);
  });

  it("maps terms to academic years and plan years", () => {
    expect(yearIndex("2028-SP", "2026-AU")).toBe(2);
    expect(yearIndex("2026-SU", "2026-AU")).toBe(1);
    expect(termAt("2026-AU", 1, "AU")).toBe("2026-AU");
    expect(termAt("2026-AU", 1, "SU")).toBe("2026-SU");
    expect(termAt("2026-AU", 2, "WI")).toBe("2028-WI");
    expect(termAt("2027-WI", 1, "SU")).toBe("2026-SU");
  });

  it("resolves relative term refs", () => {
    expect(resolveTermRef("Y2-SP", "2026-AU")).toBe("2028-SP");
    expect(resolveTermRef("Y1-SU", "2026-AU")).toBe("2026-SU");
    expect(resolveTermRef("2030-AU", "2026-AU")).toBe("2030-AU");
    expect(() => resolveTermRef("Y2-XX", "2026-AU")).toThrow();
    expect(() => resolveTermRef("26-AU", "2026-AU")).toThrow();
  });

  it("labels and lists terms, Summer first and nothing after the last quarter", () => {
    expect(termLabel("2027-WI")).toBe("Winter 2027");
    expect(academicYearLabel(2026)).toBe("2026–27");
    expect(planTerms("2026-AU", "2027-SP")).toEqual(["2026-SU", "2026-AU", "2027-WI", "2027-SP"]);
    expect(planTerms("2026-AU", "2028-WI")).toEqual(["2026-SU", "2026-AU", "2027-WI", "2027-SP", "2027-SU", "2027-AU", "2028-WI"]);
    expect(catalogYearFor(new Date(2026, 10, 12))).toBe("2026-27");
    expect(catalogYearFor(new Date(2027, 2, 1))).toBe("2026-27");
  });
});

describe("graduation quarter (FEEDBACK F3)", () => {
  it("defaults to the Spring of the last year left", () => {
    expect(defaultGraduationTerm("2026-AU", 1)).toBe("2030-SP");
    expect(defaultGraduationTerm("2026-AU", 2)).toBe("2029-SP");
    expect(defaultGraduationTerm("2026-AU", 3)).toBe("2028-SP");
    expect(defaultGraduationTerm("2026-AU", 4)).toBe("2027-SP");
    expect(planYearCount("2026-AU", defaultGraduationTerm("2026-AU", 2))).toBe(3);
  });

  it("uses the plan's own graduation quarter when set", () => {
    expect(graduationTerm({ entry_term: "2026-AU", entry_year_level: 1, graduation_term: "2030-WI" })).toBe("2030-WI");
    expect(graduationTerm({ entry_term: "2026-AU", entry_year_level: 2, graduation_term: null })).toBe("2029-SP");
  });

  it("names years by class year", () => {
    expect(classYearLabel(1, 1)).toBe("First year");
    expect(classYearLabel(1, 2)).toBe("Second year");
    expect(classYearLabel(3, 2)).toBe("Fourth year");
    expect(classYearLabel(5, 1)).toBe("Fifth year");
    expect(classYearLabel(9, 1)).toBe("Year 9");
  });
});
