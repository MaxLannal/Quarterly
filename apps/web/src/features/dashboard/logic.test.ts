import { describe, expect, it } from "vitest";
import { patched, type Profile } from "./api";
import { answeredTopics, keepAll, memberSince, memoryPatch, newFacts, ownWords, withItem } from "./logic";

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
});

describe("member since", () => {
  it("speaks in days, then months", () => {
    const now = new Date(2026, 10, 20);
    expect(memberSince("2026-11-20", now)).toBe("joined today");
    expect(memberSince("2026-11-17", now)).toBe("joined 3 days ago");
    expect(memberSince("2026-09-02", now)).toBe("member since September 2026");
  });
});
