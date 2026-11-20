import { describe, expect, it } from "vitest";
import { optimisticRoutes, patched, type Profile, type Route, type RouteList } from "./api";
import { answeredTopics, byYear, entryTermFor, keepAll, memberSince, memoryPatch, newFacts, ownWords, routePlanState, withItem } from "./logic";

function profile(over: Partial<Profile> = {}): Profile {
  return {
    username: "fake-user",
    email: "fake@example.invalid",
    member_since: "2026-11-01",
    class_year: null,
    intended_programs: [],
    programs: [],
    interests: ["Physics"],
    research_areas: [],
    humanities_goal: null,
    humanities_topics: [],
    humanities_note: null,
    career_plans: null,
    career_paths: [],
    future_domains: [],
    constraints: [],
    workload: null,
    feed_categories: [],
    portrait: { headline: "", summary: "", themes: [] },
    interview: { covered: ["class_year"], turns: [] },
    follows: { threads: [], courses: [] },
    completeness: 0.14,
    updated_day: "2026-11-20",
    ...over,
  };
}

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

describe("noted facts", () => {
  it("lists only what is new, and keeping merges with the profile at that moment", () => {
    const p = profile();
    const facts = newFacts(p, { interests: ["Physics", "Greek tragedy", "Film"], class_year: 2029, humanities_goal: "enjoy" });
    expect(facts.map((f) => f.value)).toEqual(["Class of 2029", "Greek tragedy", "Film", "To enjoy specific topics"]);
    const film = facts.find((f) => f.value === "Film");
    expect(film?.keep(profile({ interests: ["Physics", "Poetry"] }))).toEqual({ interests: ["Physics", "Poetry", "Film"] });
    expect(keepAll(p, facts)).toEqual({ class_year: 2029, interests: ["Physics", "Greek tragedy", "Film"], humanities_goal: "enjoy" });
  });

  it("offers the portrait once", () => {
    const facts = newFacts(profile(), { portrait: { headline: "A physicist", summary: "s", themes: ["a"] } });
    expect(facts).toHaveLength(1);
    expect(facts[0]?.keep(profile())).toEqual({ portrait: { headline: "A physicist", summary: "s", themes: ["a"] } });
    expect(newFacts(profile({ portrait: { headline: "A physicist", summary: "s", themes: [] } }), { portrait: { headline: "A physicist", summary: "", themes: [] } })).toEqual([]);
  });

  it("dedupes items case-insensitively", () => {
    expect(withItem(["Physics"], " physics ")).toEqual(["Physics"]);
    expect(withItem(["Physics"], "Film")).toEqual(["Physics", "Film"]);
  });
});

describe("the guide's memory", () => {
  it("keeps the last 24 turns and every answered topic", () => {
    const turns = [
      { role: "guide" as const, text: "Which class?", topic: "class_year" as const },
      { role: "student" as const, text: "2029" },
      { role: "guide" as const, text: "Interests?", topic: "interests" as const },
    ];
    expect(answeredTopics(turns)).toEqual(["class_year"]);
    const many = Array.from({ length: 30 }, (_, i) => ({ role: "student" as const, text: `t${i}` }));
    const patch = memoryPatch(profile({ interview: { covered: ["research"], turns: [] } }), [...turns, ...many]);
    expect(patch.interview?.covered).toEqual(["class_year", "interests", "research"]);
    expect(patch.interview?.turns).toHaveLength(24);
  });

  it("weaves the student's own words, once each", () => {
    expect(ownWords(profile({ interests: ["Film", "film"], future_domains: ["Quantum computing"] }))).toEqual(["Film", "Quantum computing"]);
  });
});

describe("patches", () => {
  it("apply like the server: only sent fields, null clears", () => {
    const next = patched(profile({ class_year: 2029 }), { class_year: null, research_areas: ["Lasers"], interests: null });
    expect(next.class_year).toBeNull();
    expect(next.research_areas).toEqual(["Lasers"]);
    expect(next.interests).toEqual([]);
    expect(next.interview.covered).toEqual(["class_year"]);
  });

  it("choosing a route opens the one chosen before", () => {
    const list: RouteList = { items: [route({ id: "a", status: "chosen" }), route({ id: "b" })], chosen_id: "a", max_routes: 12 };
    const next = optimisticRoutes(list, "b", { status: "chosen" });
    expect(next.items.map((r) => r.status)).toEqual(["open", "chosen"]);
    expect(next.chosen_id).toBe("b");
    expect(optimisticRoutes(next, "b", { status: "open" }).chosen_id).toBeNull();
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
