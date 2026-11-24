/**
 * MSW handlers for the Catalog page's browse rows (issue #19): `/catalog/browse` builds the rows
 * from the mock catalog (fake courses only), and `/course-ratings` answers for a logged-in
 * student only, like the server. Forum quotes, like the server's, only for a logged-in reader.
 */
import { http, HttpResponse, type HttpHandler } from "msw";
import type { components } from "@/api/schema";
import { allCourses } from "./data";

type S = components["schemas"];
const A = "*/api";

const SESSION_FLAG = "quarterly.mock.session";
function loggedIn(): boolean {
  try {
    return globalThis.sessionStorage?.getItem(SESSION_FLAG) === "1";
  } catch {
    return false;
  }
}

const CORE = { key: "core", label: "The Core", motif: "arches" };
const COMPUTING = { key: "computing", label: "Computer & Data Science", motif: "circuit" };

function spotlights(): S["CourseItem"][] {
  return allCourses().map((c, i) => {
    const cat = c.code.startsWith("FAKE") ? CORE : COMPUTING;
    return {
      kind: "course",
      id: `course:${c.code}`,
      code: c.code,
      title: c.title,
      subject: c.code.split(" ")[0] ?? "TEST",
      category: cat,
      units: 100,
      excerpt: `A fake catalog description of ${c.title}, for tests only.`,
      core_tags: c.core_tags ?? [],
      illustration: { seed: 1000 + i * 7919, motif: cat.motif, palette: i % 6 },
      stats: c.hours != null ? { workload_hours: c.hours, difficulty: c.difficulty ?? null, n: c.n ?? 0 } : null,
      reason: `Best of UChicago: ${cat.label}`,
      commons_count: 0,
    };
  });
}

function quotes(): S["CommentItem"][] {
  const out: S["CommentItem"][] = [
    {
      kind: "comment",
      id: "comment:commons:2",
      snippet: "Fake answer: take the first course in Autumn; it sets up the rest.",
      course: { code: "TEST 10000", title: "Fake Introduction I" },
      category: COMPUTING,
      handle: "fake-heron",
      voice: "reply",
      source: "commons",
      href: "/forum/t/1",
      day: "2099-01-02",
    },
  ];
  if (loggedIn()) {
    out.push({
      kind: "comment",
      id: "comment:post:7",
      snippet: "Fake review: hard but fair; office hours help a lot.",
      course: { code: "TEST 20000", title: "Fake Theory" },
      category: COMPUTING,
      handle: "fake-otter",
      voice: "review",
      source: "forum",
      href: "/courses/TEST%2020000/i/fake-instructor-a/t/7",
      day: "2099-01-01",
    });
  }
  return out;
}

function newCourses(): S["NewCourse"][] {
  return [
    {
      code: "TEST 10100",
      title: "Fake Introduction II",
      units: 100,
      core_tags: [],
      excerpt: "A fake catalog description, for tests only.",
      basis: "listed",
      reason: "New in 2099-00",
      source_url: "https://example.invalid/fake-new-courses",
      source_quote: "Fake quote: TEST 10100 is new this year.",
    },
  ];
}

/** Fake ratings: TEST 10000 has reviews; every other course has none yet. */
function rating(code: string): S["RatingSummary"] {
  if (code === "TEST 10000") {
    return { n_reviews: 3, overall: 4.2, difficulty: 3.1, intellectual_intensity: 3.5, workload_hours: 9, recommend_rate: 0.67, pace: null, grading_strictness: null };
  }
  return { n_reviews: 0 };
}

export const browseHandlers: HttpHandler[] = [
  http.get(`${A}/catalog/browse`, () =>
    HttpResponse.json({ catalog_year: "2099-00", new_courses: newCourses(), spotlights: spotlights(), quotes: quotes() } satisfies S["CatalogBrowse"]),
  ),
  http.get(`${A}/course-ratings`, ({ request }) => {
    if (!loggedIn()) return HttpResponse.json({ detail: "Log in to continue." } satisfies S["ErrorOut"], { status: 401 });
    const codes = (new URL(request.url).searchParams.get("codes") ?? "").split(",").filter(Boolean);
    return HttpResponse.json({ ratings: Object.fromEntries(codes.map((c) => [c, rating(c)])) } satisfies S["CourseRatings"]);
  }),
];
