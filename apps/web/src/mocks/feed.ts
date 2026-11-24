/**
 * MSW handlers for the campus companion's "feed" endpoints (docs/BEST-OF-UCHICAGO-PLAN.md):
 * `/feed` pages through a small mixed stream built from the mock catalog (fake courses only),
 * `/feed/categories` lists the categories, `/agents/feed-notes` answers with the deterministic
 * reasons (no model involved).
 */
import { http, HttpResponse, type HttpHandler } from "msw";
import type { components } from "@/api/schema";
import { allCourses, PROGRAMS } from "./data";

type S = components["schemas"];
type FeedItem = S["FeedPage"]["items"][number];
const A = "*/api";

const CATEGORIES: S["FeedCategory"][] = [
  { key: "core", label: "The Core", motif: "arches", blurb: "The shared conversation every College student joins.", subjects: ["FAKE"], course_count: 5 },
  { key: "computing", label: "Computer & Data Science", motif: "circuit", blurb: "Algorithms, systems and machine learning.", subjects: ["TEST"], course_count: 9 },
  { key: "literature", label: "Literature & Writing", motif: "pages", blurb: "Novels, poems and essays to read closely.", subjects: [], course_count: 0 },
  { key: "more", label: "Interdisciplinary", motif: "constellation", blurb: "Courses that cross the lines.", subjects: [], course_count: 0 },
];

const ref = (key: string) => {
  const c = CATEGORIES.find((x) => x.key === key) ?? CATEGORIES[0]!;
  return { key: c.key, label: c.label, motif: c.motif };
};

function stream(): FeedItem[] {
  const courses = allCourses();
  const out: FeedItem[] = [];
  courses.forEach((c, i) => {
    const cat = c.code.startsWith("FAKE") ? "core" : "computing";
    out.push({
      kind: "course",
      id: `course:${c.code}`,
      code: c.code,
      title: c.title,
      subject: c.code.split(" ")[0] ?? "TEST",
      category: ref(cat),
      units: 100,
      excerpt: `A fake catalog description of ${c.title}, for tests only.`,
      core_tags: c.core_tags ?? [],
      words: ["fake", "catalog", "words", "for", "tests", c.title.split(" ").pop() ?? "course"].filter((w) => w.length > 2),
      illustration: { seed: 1000 + i * 7919, motif: ref(cat).motif, palette: i % 6 },
      books: i % 3 === 0 ? [{ id: "book:the-odyssey", slug: "the-odyssey", title: "The Odyssey", author: "Homer", year: -725, when: "8th century BCE" }] : [],
      stats: c.hours != null ? { workload_hours: c.hours, difficulty: c.difficulty ?? null, n: c.n ?? 0 } : null,
      reason: `Best of UChicago: ${ref(cat).label}`,
      commons_count: 0,
    });
    if (i === 2) {
      out.push({
        kind: "book",
        id: "book:the-odyssey",
        book: { id: "book:the-odyssey", slug: "the-odyssey", title: "The Odyssey", author: "Homer", year: -725, when: "8th century BCE" },
        category: ref("literature"),
        courses: courses.slice(0, 2).map((x) => ({ code: x.code, title: x.title })),
        reason: "From the shelf for Literature & Writing",
      });
    }
    if (i === 5) {
      out.push({
        kind: "words",
        id: "words:computing",
        category: ref("computing"),
        label: "Computer & Data Science",
        words: ["fake", "systems", "theory", "methods", "learning", "networks", "graphics", "introduction", "elective", "survey", "studio", "humanities"].map((text, k) => ({ text, weight: (k % 5) + 1 })),
      });
    }
    if (i === 8) {
      const p = PROGRAMS[1]!;
      out.push({ kind: "program", id: `program:${p.id}`, program_id: p.id, name: p.name, type: p.type, department: p.department ?? null, reason: "A major worth a look" });
    }
  });
  return out;
}

export const feedHandlers: HttpHandler[] = [
  http.get(`${A}/feed/categories`, () => HttpResponse.json({ categories: CATEGORIES, selected: [] } satisfies S["FeedCategories"])),
  http.get(`${A}/feed`, ({ request }) => {
    const url = new URL(request.url);
    const tab = (url.searchParams.get("tab") ?? "for_you") as S["FeedPage"]["tab"];
    const limit = Number(url.searchParams.get("limit") ?? 12);
    const offset = Number(url.searchParams.get("cursor") ?? 0) || 0;
    const all = tab === "following" ? [] : stream();
    const items = all.slice(offset, offset + limit);
    const end = offset + items.length;
    const page: S["FeedPage"] = {
      tab,
      items,
      next_cursor: end < all.length ? String(end) : null,
      categories_applied: (url.searchParams.get("categories") ?? "").split(",").filter(Boolean),
      headline: tab === "following" ? "Nothing to follow yet: follow a course" : "Today's river: fake introductions and fake theory",
      personalized: false,
    };
    return HttpResponse.json(page);
  }),
  http.post(`${A}/agents/feed-notes`, async ({ request }) => {
    const body = (await request.json()) as S["FeedNotesRequest"];
    const reasons = new Map(stream().map((i) => [i.id, "reason" in i ? i.reason : "From the feed"]));
    const notes = Object.fromEntries(body.item_ids.filter((id) => reasons.has(id)).map((id) => [id, reasons.get(id)!]));
    return HttpResponse.json({ headline: "Today's river: fake introductions and fake theory", notes, ai: false } satisfies S["FeedNotes"]);
  }),
];
