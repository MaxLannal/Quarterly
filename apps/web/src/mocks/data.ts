/**
 * Mock catalog for MSW. Everything here is deliberately fake (TEST/FAKE subjects, "Fake Program",
 * catalog year 2099-00) so it can never be mistaken for UChicago catalog facts.
 */
import type {
  AttributeValue,
  CatalogYear,
  CourseDetail,
  CourseSummary,
  Expr,
  OfferingPattern,
  ProgramDetail,
  ProgramSummary,
  Quarter,
  Source,
  Term,
} from "@/api/types";
import type { components } from "@/api/schema";

export const MOCK_CATALOG_YEAR = "2099-00";
export const FAKE_SOURCE: Source = { quote: "Fake source text for tests; not a catalog quote.", url: null };

interface FakeCourse {
  code: string;
  title: string;
  quarters: Quarter[];
  prereq?: string[];
  hours?: number;
  difficulty?: number;
  /** Number of forum ratings; below 3 the value is shown as an estimate. */
  n?: number;
  core_tags?: string[];
  tags?: string[];
}

const COURSES: FakeCourse[] = [
  { code: "TEST 10000", title: "Fake Introduction I", quarters: ["AU"], hours: 8, difficulty: 2 },
  { code: "TEST 10100", title: "Fake Introduction II", quarters: ["WI"], prereq: ["TEST 10000"], hours: 9, difficulty: 2.5 },
  { code: "TEST 10200", title: "Fake Introduction III", quarters: ["SP"], prereq: ["TEST 10100"], hours: 10, difficulty: 3 },
  { code: "TEST 20000", title: "Fake Theory", quarters: ["AU", "WI"], prereq: ["TEST 10200"], hours: 14, difficulty: 4, n: 12 },
  { code: "TEST 20100", title: "Fake Systems", quarters: ["WI", "SP"], prereq: ["TEST 10200"], hours: 15, difficulty: 4.2, n: 9 },
  { code: "TEST 20200", title: "Fake Methods", quarters: ["AU", "SP"], prereq: ["TEST 10100"], hours: 11, difficulty: 3.1 },
  { code: "TEST 25000", title: "Fake Elective in Learning", quarters: ["AU", "SP"], prereq: ["TEST 20000"], hours: 12, difficulty: 3.5, tags: ["ml"] },
  { code: "TEST 25100", title: "Fake Elective in Networks", quarters: ["WI"], hours: 10, difficulty: 3 },
  { code: "TEST 25200", title: "Fake Elective in Graphics", quarters: ["SP"], hours: 13, difficulty: 3.4, n: 34 },
  { code: "FAKE 11000", title: "Fake Humanities I", quarters: ["AU"], hours: 7, difficulty: 2, core_tags: ["huma"] },
  { code: "FAKE 11100", title: "Fake Humanities II", quarters: ["WI"], prereq: ["FAKE 11000"], hours: 7, difficulty: 2, core_tags: ["huma"] },
  { code: "FAKE 11200", title: "Fake Humanities III", quarters: ["SP"], prereq: ["FAKE 11100"], hours: 7, difficulty: 2, core_tags: ["huma"] },
  { code: "FAKE 13000", title: "Fake Arts Studio", quarters: ["AU", "WI", "SP"], hours: 6, difficulty: 1.5, core_tags: ["arts"] },
  { code: "FAKE 14000", title: "Fake Science Survey", quarters: ["AU", "WI", "SP", "SU"], hours: 9, difficulty: 2.5, core_tags: ["sci"] },
];

function attributes(c: FakeCourse): AttributeValue[] {
  const n = c.n ?? 0;
  const method = n >= 3 ? "forum" : "prior";
  const out: AttributeValue[] = [];
  if (c.hours != null) {
    out.push({ subject_type: "course", subject_id: c.code, key: "workload_hours", value: c.hours, ci_low: c.hours - 2, ci_high: c.hours + 2, n, method });
  }
  if (c.difficulty != null) {
    out.push({ subject_type: "course", subject_id: c.code, key: "difficulty", value: c.difficulty, ci_low: null, ci_high: null, n, method });
    out.push({ subject_type: "course", subject_id: c.code, key: "intellectual_intensity", value: Math.min(5, c.difficulty + 0.5), ci_low: null, ci_high: null, n, method });
  }
  return out;
}

export function summary(c: FakeCourse): CourseSummary {
  return {
    code: c.code,
    title: c.title,
    units: 100,
    attributes: attributes(c),
    core_tags: c.core_tags ?? [],
    crosslists: [],
    tags: c.tags ?? [],
  };
}

function prereqExpr(codes: string[] | undefined): Expr | null {
  if (!codes?.length) return null;
  const atoms: Expr[] = codes.map((value) => ({ op: "atom", atom: { kind: "course", value, min_grade: null }, children: [], n: null }));
  return atoms.length === 1 ? (atoms[0] as Expr) : { op: "all", children: atoms, n: null, atom: null };
}

function offerings(c: FakeCourse): OfferingPattern[] {
  return (["AU", "WI", "SP", "SU"] as Quarter[]).map((quarter) => ({
    course: c.code,
    quarter,
    p_offered: c.quarters.includes(quarter) ? 0.95 : quarter === "SU" ? 0 : 0.05,
    method: "catalog",
    evidence_terms: [],
  }));
}

export const FAKE_INSTRUCTOR = { slug: "fake-instructor-a", display_name: "Fake Instructor A", department: "Fake Department" };

export function findCourse(code: string): FakeCourse | undefined {
  return COURSES.find((c) => c.code === code);
}

export function allCourses(): FakeCourse[] {
  return COURSES;
}

export function prereqsOf(code: string): string[] {
  return findCourse(code)?.prereq ?? [];
}

export function offeredIn(code: string, quarter: Quarter): boolean {
  return findCourse(code)?.quarters.includes(quarter) ?? false;
}

export function detail(c: FakeCourse): CourseDetail {
  const unlocks = COURSES.filter((o) => o.prereq?.includes(c.code)).map((o) => o.code);
  return {
    ...summary(c),
    catalog_year: MOCK_CATALOG_YEAR,
    description: `${c.title} is a fake course used to exercise the interface. It does not exist.`,
    prereq: prereqExpr(c.prereq),
    prereq_text: c.prereq?.length ? `${c.prereq.join(" and ")}.` : null,
    prereq_human: c.prereq?.length ? c.prereq.join(" and ") : null,
    coreq: null,
    restrictions: null,
    notes: null,
    needs: c.prereq ?? [],
    unlocks,
    offerings: offerings(c),
    sections: [
      { course: c.code, term: c.quarters[0] === "AU" ? "2099-AU" : `2100-${c.quarters[0] ?? "WI"}`, section_no: "1", component: "LEC", instructor_ids: [FAKE_INSTRUCTOR.slug], meetings: [], status: "open" },
    ],
    instructors: [{ instructor: FAKE_INSTRUCTOR, page_id: COURSES.indexOf(c) + 1, n_terms: 2, first_term: "2099-AU", last_term: "2100-SP" }],
    relations: [],
    counts_toward: [],
    source: FAKE_SOURCE,
  };
}

// ------------------------------------------------------------------------------------------
// Programs
// ------------------------------------------------------------------------------------------

type S = components["schemas"];
const select = (id: string, label: string, count: number, from: S["Selector"]): S["SelectNode"] => ({
  kind: "select",
  id,
  label,
  count,
  from,
  units: null,
  needs_review: false,
  weight: 1,
  source: FAKE_SOURCE,
});

const PROGRAM_RULES: Record<string, RuleRoot> = {
  "fake-core": {
    kind: "group",
    id: null,
    label: "Fake Core",
    all: true,
    n_of: null,
    needs_review: false,
    weight: 1,
    source: FAKE_SOURCE,
    children: [
      select("huma", "Fake Humanities sequence", 3, { codes: ["FAKE 11000", "FAKE 11100", "FAKE 11200"] }),
      { kind: "slot", id: "arts", label: "Fake Arts", any_of: ["FAKE 13000"], needs_review: false, weight: 1, source: FAKE_SOURCE },
      select("sci", "Fake Science", 1, { tags: ["core:sci"] }),
    ],
  },
  "fake-major": {
    kind: "group",
    id: null,
    label: "Fake Program",
    all: true,
    n_of: null,
    needs_review: false,
    weight: 1,
    source: FAKE_SOURCE,
    children: [
      select("intro", "Fake introductory sequence", 3, { codes: ["TEST 10000", "TEST 10100", "TEST 10200"] }),
      select("core", "Fake core courses", 2, { codes: ["TEST 20000", "TEST 20100", "TEST 20200"] }),
      select("electives", "Fake electives", 2, { subject: "TEST", number_range: [25000, 29999] }),
    ],
  },
  "fake-minor": {
    kind: "bounded_parts",
    id: null,
    label: "Fake Minor",
    needs_review: true,
    weight: 1,
    source: FAKE_SOURCE,
    total: { courses: 3, units: null },
    parts: [
      { id: "theory", label: "Fake theory part", count: [1, 2], from: { codes: ["TEST 20000", "TEST 20200"] }, needs_review: true, source: FAKE_SOURCE },
      { id: "applied", label: "Fake applied part", count: [1, 3], from: { subject: "TEST", number_range: [25000, 29999] }, needs_review: true, source: FAKE_SOURCE },
    ],
  },
  "fake-abroad": {
    kind: "slot",
    id: null,
    label: "Fake Study Abroad Block",
    any_of: ["FAKE 14000"],
    needs_review: false,
    weight: 1,
    source: FAKE_SOURCE,
  },
};
type RuleRoot = ProgramDetail["rules"];

export const PROGRAMS: ProgramSummary[] = [
  { id: "fake-core", name: "Fake Core", type: "core", status: "published", catalog_year: MOCK_CATALOG_YEAR, degree: null, department: "Fake College", parent_id: null, verified_at: "2099-07-01" },
  { id: "fake-major", name: "Fake Program", type: "major", status: "published", catalog_year: MOCK_CATALOG_YEAR, degree: "BA", department: "Fake Department", parent_id: null, verified_at: "2099-07-01" },
  { id: "fake-minor", name: "Fake Minor", type: "minor", status: "review", catalog_year: MOCK_CATALOG_YEAR, degree: null, department: "Fake Department", parent_id: null, verified_at: null },
  { id: "fake-abroad", name: "Fake Study Abroad Block", type: "study_abroad_block", status: "published", catalog_year: MOCK_CATALOG_YEAR, degree: null, department: "Fake Study Abroad", parent_id: null, verified_at: "2099-07-01" },
];

export function programDetail(id: string): ProgramDetail | undefined {
  const s = PROGRAMS.find((p) => p.id === id);
  const rules = PROGRAM_RULES[id];
  if (!s || !rules) return undefined;
  return {
    ...s,
    checksum: `fake-${id}`,
    policy: { excludes: [], requires: [], share: [], residency: null, timing: null },
    rules,
    sample_path: id === "fake-major"
      ? [
          { course: "TEST 10000", term: "2099-AU", status: "planned", locked: false, grading: "letter" },
          { course: "TEST 10100", term: "2100-WI", status: "planned", locked: false, grading: "letter" },
          { course: "TEST 10200", term: "2100-SP", status: "planned", locked: false, grading: "letter" },
        ]
      : [],
    sources: [{ quote: FAKE_SOURCE.quote, url: null }],
    verified_by: s.verified_at ? "fake-curator" : null,
    version_id: PROGRAMS.indexOf(s) + 1,
  };
}

export const CATALOG_YEARS: CatalogYear[] = [{ id: MOCK_CATALOG_YEAR, published_at: null }];

export function mockTerms(): Term[] {
  const out: Term[] = [];
  for (let y = 2099; y < 2105; y += 1) {
    out.push({ id: `${y}-AU`, start: null, end: null });
    for (const q of ["WI", "SP", "SU"]) out.push({ id: `${y + 1}-${q}`, start: null, end: null });
  }
  return out;
}

/** Does a fake course match a selector (subset of the server's semantics, for mocks only)? */
export function matches(code: string, sel: S["Selector"]): boolean {
  const c = findCourse(code);
  if (!c) return false;
  if (sel.exclude?.includes(code)) return false;
  const [subject, num] = code.split(" ");
  const n = Number(num);
  if (sel.codes?.length && !sel.codes.includes(code)) return false;
  if (sel.subject && sel.subject !== subject) return false;
  if (sel.number_range && (n < sel.number_range[0] || n > sel.number_range[1])) return false;
  if (sel.tags?.length) {
    const tags = new Set([...(c.tags ?? []), ...(c.core_tags ?? []).map((t) => `core:${t}`)]);
    if (!sel.tags.some((t) => tags.has(t))) return false;
  }
  if (sel.union?.length && !sel.union.some((u) => matches(code, u))) return false;
  return true;
}
