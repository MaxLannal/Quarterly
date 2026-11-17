/**
 * MSW handlers for the curator review queue (prompt 09). In-memory and FAKE: a made-up
 * "Fake Science (BS)" program version proposed by the ingestion pipeline, a prerequisite the
 * pipeline could not check, and a course batch. Admin-only, like the real API: set
 * sessionStorage "quarterly.mock.admin" = "1" (see src/mocks/forum.ts).
 */
import { http, HttpResponse } from "msw";
import type { components } from "@/api/schema";
import { ADMIN_FLAG } from "./forum";

type S = components["schemas"];
type Item = S["ReviewItemOut"];
const A = "*/api";
const PAGE = "https://example.test/fake-catalog/fakescience/";

function flag(name: string): boolean {
  try {
    return globalThis.sessionStorage?.getItem(name) === "1";
  } catch {
    return false;
  }
}
function json<T>(body: T, status = 200) {
  return HttpResponse.json(body as never, { status });
}
const err = (detail: string, status: number) => json<S["ErrorOut"]>({ detail }, status);
const today = () => new Date().toISOString().slice(0, 10);

const FAKE_RULES = {
  id: "fake-science-bs",
  catalog_year: "2099-00",
  type: "major",
  rules: {
    id: "fake-science-bs",
    kind: "group",
    all: true,
    children: [
      { id: "intro", kind: "slot", any_of: ["TEST 10000"], source: { url: PAGE, quote: "FAKE: students take TEST 10000." } },
      { id: "methods", kind: "slot", any_of: ["TEST 20000"], source: { url: PAGE, quote: "FAKE: the BS also requires TEST 20000." } },
    ],
    source: { url: PAGE, quote: "FAKE: the fake science program offers a BS." },
  },
};

function seedItems(): Item[] {
  return [
    {
      id: 1,
      target_type: "program_version",
      target_id: "41",
      title: "fake-science-bs 2099-00",
      reason: "fake-science-bs: new program; checks to look at: (d) Two runs agree",
      status: "open",
      decided_at: null,
      program_version_id: 41,
      program_version_status: "review",
      decision_hint: "review",
      diff: { kind: "program_version", program_id: "fake-science-bs", catalog_year: "2099-00", rules: FAKE_RULES },
      nodes: [
        { path: "fake-science-bs", kind: "group", label: "Fake Science BS", summary: "All of the following", quote: "FAKE: the fake science program offers a BS.", url: PAGE, snapshot_id: "7", flags: [] },
        { path: "fake-science-bs/intro", kind: "slot", label: "Introduction", summary: "TEST 10000", quote: "FAKE: students take TEST 10000.", url: PAGE, snapshot_id: "7", flags: [] },
        {
          path: "fake-science-bs/methods",
          kind: "slot",
          label: "Methods",
          summary: "TEST 20000 (no pass/fail)",
          quote: "FAKE: the BS also requires TEST 20000.",
          url: PAGE,
          snapshot_id: "7",
          flags: ["The second run disagrees here (different)."],
        },
      ],
      checks: [
        { id: "a", name: "Schema", ok: true, skipped: false, problems: [] },
        { id: "c", name: "Quotes are verbatim", ok: true, skipped: false, problems: [] },
        { id: "d", name: "Two runs agree", ok: false, skipped: false, problems: ["fake-science-bs/methods: different"] },
        { id: "f", name: "Golden plans", ok: true, skipped: true, problems: ["no golden plans for this program"] },
      ],
    },
    {
      id: 2,
      target_type: "requisite",
      target_id: "2099-00:TEST 20000",
      title: "Prerequisite of TEST 20000 2099-00",
      reason: "Prerequisite needs a person: names TEST 99999, which is not in the catalog",
      status: "open",
      decided_at: null,
      program_version_id: null,
      program_version_status: null,
      decision_hint: null,
      diff: {
        kind: "requisite",
        course: "TEST 20000",
        raw_text: "FAKE: TEST 10000 or TEST 99999.",
        proposed: { op: "any", children: [{ op: "atom", atom: { kind: "course", value: "TEST 10000" } }] },
        proposed_text: "TEST 10000",
        errors: ["names TEST 99999, which is not in the catalog"],
      },
      nodes: [],
      checks: [],
    },
    {
      id: 3,
      target_type: "course_batch",
      target_id: "2099-00:TEST",
      title: "TEST courses 2099-00",
      reason: "TEST: 1 new, 0 changed, 0 removed since 2098-99",
      status: "open",
      decided_at: null,
      program_version_id: null,
      program_version_status: null,
      decision_hint: null,
      diff: { kind: "course_batch", subject: "TEST", added: ["TEST 30000"], changed: [], removed: [], courses: [] },
      nodes: [],
      checks: [],
    },
  ];
}

let items: Item[] = seedItems();

export function resetReviewMock() {
  items = seedItems();
}

export const reviewHandlers = [
  http.get(`${A}/admin/review-items`, ({ request }) => {
    if (!flag(ADMIN_FLAG)) return err("Only admins can use the review queue.", 403);
    const status = new URL(request.url).searchParams.get("status") ?? "open";
    const rows = items.filter((i) => i.status === status);
    return json<S["Page_ReviewItemOut_"]>({ items: rows, total: rows.length, limit: 200, offset: 0 });
  }),
  http.post(`${A}/admin/review-items/:id/decision`, async ({ params, request }) => {
    if (!flag(ADMIN_FLAG)) return err("Only admins can use the review queue.", 403);
    const item = items.find((i) => i.id === Number(params.id));
    if (!item) return err("Review item not found.", 404);
    if (item.status !== "open") return err(`This item was already decided (${item.status}).`, 409);
    const body = (await request.json()) as S["ReviewDecision"];
    if (body.decision === "edit" && item.target_type === "course_batch") return err("Course batches cannot be edited here.", 422);
    if (body.decision === "edit" && item.target_type === "program_version" && !body.edited?.rules) return err("Send the edited rule tree as `edited.rules`.", 422);
    item.status = body.decision === "reject" ? "rejected" : "accepted";
    item.decided_at = today();
    if (item.target_type === "program_version" && body.decision === "reject") item.program_version_status = "draft";
    return json<Item>(item);
  }),
  http.post(`${A}/admin/program-versions/:id/publish`, ({ params }) => {
    if (!flag(ADMIN_FLAG)) return err("Only admins can use the review queue.", 403);
    const id = Number(params.id);
    const related = items.filter((i) => i.program_version_id === id);
    if (!related.length) return err("Program version not found.", 404);
    if (related.some((i) => i.status === "open")) return err("Decide the open review items for this version first.", 409);
    if (related.some((i) => i.program_version_status !== "review")) return err("Only a version in review can be published.", 409);
    for (const i of related) i.program_version_status = "published";
    return json<S["ProgramVersionOut"]>({
      id,
      program_id: "fake-science-bs",
      catalog_year: "2099-00",
      status: "published",
      verified_by: "fake-admin",
      verified_at: today(),
      checksum: "sha256:fake",
    });
  }),
];
