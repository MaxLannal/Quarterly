/**
 * Pure helpers of the dashboard (tested in logic.test.ts): what the guide noted that is new,
 * the patch that keeps one noted fact, the guide's memory, the words woven into the hero, and
 * small formatters. (The route helpers went with "Your routes", issue #15.)
 */
import type { InterviewTurn, Profile, ProfilePatch, Topic } from "./api";

export const CAMPUS_YEAR = "2026-27";
export const TOPICS: Topic[] = ["class_year", "interests", "humanities", "research", "career", "future", "constraints", "wrapup"];
export const TOPIC_LABELS: Record<Topic, string> = {
  class_year: "Class year",
  interests: "Interests",
  humanities: "Humanities",
  research: "Research",
  career: "Career",
  future: "Horizons",
  constraints: "Workload",
  wrapup: "Portrait",
};
export const MAX_ITEMS = 24;
export const MAX_ITEM_CHARS = 60;
export const MAX_TURNS = 24;

export type ListField = "interests" | "research_areas" | "humanities_topics" | "career_paths" | "future_domains" | "constraints";
export const LIST_LABELS: Record<ListField, string> = {
  interests: "Interest",
  research_areas: "Research",
  humanities_topics: "Humanities topic",
  career_paths: "Career path",
  future_domains: "Horizon",
  constraints: "Constraint",
};
const LIST_FIELDS = Object.keys(LIST_LABELS) as ListField[];

export const GOAL_LABELS = {
  pass: "Just to pass",
  balance: "A balance",
  enjoy: "To enjoy specific topics",
  deep: "To go deep",
} as const;
export type Goal = keyof typeof GOAL_LABELS;

export const WORKLOAD_LABELS = { light: "Light", balanced: "Balanced", intense: "Intense" } as const;
export type Workload = keyof typeof WORKLOAD_LABELS;

/** One fact the guide noted, shown as a "Noted" chip the student keeps or drops. */
export interface Fact {
  id: string;
  label: string;
  value: string;
  /** The patch that keeps it, given the profile at the moment it is kept. */
  keep: (profile: Profile) => ProfilePatch;
}

const fold = (s: string) => s.trim().toLocaleLowerCase();

export function hasItem(items: readonly string[], item: string): boolean {
  return items.some((i) => fold(i) === fold(item));
}

/** `items` plus `item` (if new, and while there is room). */
export function withItem(items: readonly string[], item: string): string[] {
  const clean = item.replace(/\s+/g, " ").trim().slice(0, MAX_ITEM_CHARS);
  if (!clean || hasItem(items, clean) || items.length >= MAX_ITEMS) return [...items];
  return [...items, clean];
}

export function withoutItem(items: readonly string[], item: string): string[] {
  return items.filter((i) => fold(i) !== fold(item));
}

/** The facts of a proposed patch that are not in the profile yet. */
export function newFacts(profile: Profile, proposed: ProfilePatch | undefined): Fact[] {
  if (!proposed) return [];
  const facts: Fact[] = [];
  if (proposed.class_year && proposed.class_year !== profile.class_year) {
    const year = proposed.class_year;
    facts.push({ id: `class_year:${year}`, label: "Class year", value: `Class of ${year}`, keep: () => ({ class_year: year }) });
  }
  for (const field of LIST_FIELDS) {
    const items = proposed[field];
    if (!items) continue;
    for (const item of items) {
      if (hasItem(profile[field], item)) continue;
      facts.push({
        id: `${field}:${fold(item)}`,
        label: LIST_LABELS[field],
        value: item,
        keep: (p) => ({ [field]: withItem(p[field], item) }),
      });
    }
  }
  const goal = proposed.humanities_goal;
  if (goal && goal !== profile.humanities_goal) {
    facts.push({ id: `goal:${goal}`, label: "Humanities", value: GOAL_LABELS[goal], keep: () => ({ humanities_goal: goal }) });
  }
  const workload = proposed.workload;
  if (workload && workload !== profile.workload) {
    facts.push({ id: `workload:${workload}`, label: "Workload", value: WORKLOAD_LABELS[workload], keep: () => ({ workload }) });
  }
  const plans = proposed.career_plans;
  if (plans && plans !== profile.career_plans) {
    facts.push({ id: `career_plans:${plans.slice(0, 40)}`, label: "Career plans", value: plans, keep: () => ({ career_plans: plans }) });
  }
  const note = proposed.humanities_note;
  if (note && note !== profile.humanities_note) {
    facts.push({ id: `humanities_note:${note.slice(0, 40)}`, label: "Humanities note", value: note, keep: () => ({ humanities_note: note }) });
  }
  const portrait = proposed.portrait;
  if (portrait && (portrait.headline || portrait.summary) && portrait.headline !== profile.portrait.headline) {
    facts.push({
      id: `portrait:${portrait.headline}`,
      label: "Portrait",
      value: portrait.headline || portrait.summary || "",
      keep: () => ({ portrait: { headline: portrait.headline ?? "", summary: portrait.summary ?? "", themes: portrait.themes ?? [] } }),
    });
  }
  return facts;
}

/** Several facts kept at once, in one patch. */
export function keepAll(profile: Profile, facts: Fact[]): ProfilePatch {
  let current = profile;
  let patch: ProfilePatch = {};
  for (const fact of facts) {
    const one = fact.keep(current);
    patch = { ...patch, ...one };
    current = { ...current, ...(one as Partial<Profile>) };
  }
  return patch;
}

/** Topics the conversation answered (a guide turn followed by a student turn). */
export function answeredTopics(turns: readonly InterviewTurn[]): Topic[] {
  const out = new Set<Topic>();
  let asked: Topic | null = null;
  for (const t of turns) {
    if (t.role === "guide") asked = t.topic ?? null;
    else if (asked) out.add(asked);
  }
  return TOPICS.filter((t) => out.has(t));
}

/** The topics with something on the dashboard. */
export function filledTopics(p: Profile): Topic[] {
  const filled: Record<Topic, boolean> = {
    class_year: p.class_year != null,
    interests: p.interests.length > 0,
    humanities: p.humanities_goal != null || p.humanities_topics.length > 0,
    research: p.research_areas.length > 0,
    career: !!p.career_plans || p.career_paths.length > 0,
    future: p.future_domains.length > 0,
    constraints: p.constraints.length > 0 || p.workload != null,
    wrapup: !!p.portrait.headline,
  };
  return TOPICS.filter((t) => filled[t]);
}

/** The guide's memory to save: the last turns and every topic covered so far. */
export function memoryPatch(profile: Profile, turns: readonly InterviewTurn[]): ProfilePatch {
  const covered = new Set<Topic>([...profile.interview.covered, ...answeredTopics(turns)]);
  return {
    interview: {
      covered: TOPICS.filter((t) => covered.has(t)),
      turns: turns.slice(-MAX_TURNS).map((t) => ({ role: t.role, text: t.text.slice(0, 2000), topic: t.topic ?? null })),
    },
  };
}

/** Words for the hero's drawing and the guide's background: the student's own words. */
export function ownWords(p: Profile | undefined, extra: readonly string[] = []): string[] {
  if (!p) return [...extra];
  const words = [...p.interests, ...p.future_domains, ...p.research_areas, ...p.humanities_topics, ...p.portrait.themes, ...extra];
  const out: string[] = [];
  for (const w of words) if (w && !hasItem(out, w)) out.push(w);
  return out.slice(0, 18);
}

/** "today", "yesterday", "3 days ago", "in November 2026" (day-level dates only). */
export function memberSince(day: string, now: Date = new Date()): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  const then = Date.UTC(y, m - 1, d);
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((today - then) / 86_400_000);
  if (days <= 0) return "joined today";
  if (days === 1) return "joined yesterday";
  if (days < 14) return `joined ${days} days ago`;
  const month = new Date(then).toLocaleString("en-US", { month: "long", timeZone: "UTC" });
  return `member since ${month} ${y}`;
}

/** A stable small hash of a word (seeds the horizon glyphs). */
export function hashWord(word: string): number {
  let h = 2166136261;
  for (const ch of word.toLowerCase()) {
    h ^= ch.codePointAt(0) ?? 0;
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** A small deterministic random generator. */
export function seeded(seed: number): () => number {
  let s = seed || 1;
  return () => {
    s = (Math.imul(s ^ (s >>> 15), 2246822519) + 0x9e3779b9) >>> 0;
    s ^= s >>> 13;
    return (s >>> 0) / 4294967296;
  };
}

export const courseHref = (code: string) => `/courses/${encodeURIComponent(code)}`;
export const programHref = (id: string) => `/programs/${encodeURIComponent(id)}`;
