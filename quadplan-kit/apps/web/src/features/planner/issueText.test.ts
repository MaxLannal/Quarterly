import type { Issue } from "@/api/types";
import { firstClause, hasDetails, summarizeIssue } from "./issueText";

const issue = (fields: Partial<Issue>): Issue => ({ code: "V03", level: "error", message: "", course_ids: [], term_ids: [], fix_hints: [], ...fields }) as Issue;

describe("short issue messages (FEEDBACK 'Concatenating Error Messages')", () => {
  it("shortens Richard's prerequisite example and links to the prerequisites", () => {
    const long = issue({
      message:
        "Prerequisite of MATH 20250 in 2026-AU is not met: MATH 16300 is not in the plan; MATH 16310 is not in the plan; MATH 15910 is not in the plan; MATH 15900 is not in the plan; MATH 19900 is not in the plan. Requirement: MATH 16300 or MATH 16310 or MATH 15910 or MATH 15900 or MATH 19900.",
      course_ids: ["MATH 20250"],
    });
    expect(summarizeIssue(long)).toEqual({
      card: "Prerequisite not met.",
      list: "Prerequisite of MATH 20250 not met.",
      link: { label: "View prerequisite", href: "/courses/MATH%2020250#prereq" },
    });
    expect(hasDetails(long)).toBe(true);
  });

  it("names co-requisites, restrictions and consent", () => {
    const co = summarizeIssue(issue({ message: "Co-requisite of PHYS 13300 in 2027-WI is not met: x.", course_ids: ["PHYS 13300"] }));
    expect([co.card, co.list, co.link?.label]).toEqual(["Co-requisite not met.", "Co-requisite of PHYS 13300 not met.", "View co-requisite"]);
    const consent = summarizeIssue(issue({ message: "ARTV 20000 in 2027-WI needs the consent of the instructor.", course_ids: ["ARTV 20000"], level: "warning" }));
    expect(consent.card).toBe("Needs the instructor's consent.");
  });

  it("keeps other checks to their first clause, with readable quarters", () => {
    const load = summarizeIssue(issue({ code: "V05", message: "2027-AU has 500 units: this overload needs a petition to the Dean of Students.", term_ids: ["2027-AU"] }));
    expect(load.list).toBe("Autumn 2027 has 500 units.");
    const offered = summarizeIssue(issue({ code: "V04", level: "warning", message: "HUMA 16000 is not usually offered in Summer (offered in Autumn).", course_ids: ["HUMA 16000"] }));
    expect([offered.card, offered.list]).toEqual(["Not usually offered in Summer.", "HUMA 16000: not usually offered in Summer."]);
    const twice = summarizeIssue(issue({ code: "V02", message: "MATH 15100 appears more than once and is not repeatable: 2026-AU, 2027-WI.", course_ids: ["MATH 15100"] }));
    expect([twice.card, twice.list]).toEqual(["Appears more than once and is not repeatable.", "MATH 15100 appears more than once and is not repeatable."]);
    const conflict = summarizeIssue(issue({ code: "V06", message: "A 10000 and B 10000 meet at the same time in 2027-WI.", course_ids: ["A 10000", "B 10000"] }));
    expect(conflict.card).toBe("Time conflict.");
  });

  it("finds the first clause", () => {
    expect(firstClause("One thing: the rest.")).toBe("One thing");
    expect(firstClause("Just one sentence.")).toBe("Just one sentence");
    expect(firstClause("First. Second.")).toBe("First");
  });
});
