/**
 * MSW handlers for the campus companion's "ask" endpoints (docs/BEST-OF-UCHICAGO-PLAN.md):
 * `/agents/ask` streams two tool steps and a cited answer like the server; `/me/updates` serves
 * a small "For you" list (logged in only) and `/me/updates/seen` clears it. No model involved.
 */
import { http, HttpResponse } from "msw";
import type { components } from "@/api/schema";

type S = components["schemas"];
type AskEvent = S["AskEvent"];
const A = "*/api";

const SESSION_FLAG = "quarterly.mock.session";
function loggedIn(): boolean {
  try {
    return globalThis.sessionStorage?.getItem(SESSION_FLAG) === "1";
  } catch {
    return false;
  }
}

function sse(events: AskEvent[]) {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream" } });
}

export function askReply(req: S["AskRequest"]): AskEvent[] {
  const greeting = /^\s*(hi|hello|hey)\b/i.test(req.message);
  if (greeting) {
    return [
      { type: "answer", text: "Hi! I'm Quarterly's campus guide.", citations: [], courses: [], followups: ["What is the Core curriculum?"], ai: false },
      { type: "done", run_id: "mock-run" },
    ];
  }
  return [
    { type: "step", tool: "search_courses", label: "Searching the catalog for “intro”", status: "started" },
    { type: "step", tool: "search_courses", label: "Searching the catalog for “intro”", status: "done" },
    { type: "step", tool: "campus_guide", label: "Checking the campus guide on “core”", status: "started" },
    { type: "step", tool: "campus_guide", label: "Checking the campus guide on “core”", status: "done" },
    {
      type: "answer",
      text: "Start with **TEST 10000**, then TEST 10100 in Winter.\n\n- The Core is shared by every student.\n- Ask your adviser before you choose.",
      citations: [
        { kind: "course", id: "TEST 10000", label: "TEST 10000 · Fake Introduction I", href: "/courses/TEST%2010000" },
        { kind: "guide", id: "core-overview", label: "The Core curriculum", href: "https://college.uchicago.edu/academics/core-curriculum" },
      ],
      courses: [
        { code: "TEST 10000", title: "Fake Introduction I" },
        { code: "TEST 10100", title: "Fake Introduction II" },
      ],
      followups: ["What comes after TEST 10100?", "Is TEST 10000 hard?"],
      ai: true,
    },
    { type: "done", run_id: "mock-run" },
  ];
}

let seen = false;

function updates(digest: boolean): S["UpdatesOut"] {
  const items: S["UpdateItem"][] = [
    {
      kind: "reply",
      id: 2,
      title: "New reply: Which intro sequence first?",
      snippet: "Take the first course in Autumn; it sets up the rest.",
      course_code: "TEST 10000",
      href: "/forum/t/1#reply-2",
      day: "2099-01-02",
      reason: "On a thread you follow",
      is_new: !seen,
    },
    {
      kind: "review",
      id: 7,
      title: "A new review · TEST 20000",
      snippet: "Hard but fair; office hours help a lot.",
      course_code: "TEST 20000",
      href: "/courses/TEST%2020000/i/fake-teacher/t/7",
      day: "2099-01-01",
      reason: "About TEST 20000 in your route",
      is_new: false,
    },
  ];
  return {
    items,
    unread: items.filter((i) => i.is_new).length,
    digest: digest ? "One new reply on a question you follow. Read it first." : null,
    digest_ai: digest,
  };
}

export function resetAskMock() {
  seen = false;
}

export const askHandlers = [
  http.post(`${A}/agents/ask`, async ({ request }) => sse(askReply((await request.json()) as S["AskRequest"]))),
  http.get(`${A}/me/updates`, ({ request }) => {
    if (!loggedIn()) return HttpResponse.json({ detail: "Log in to continue." } satisfies S["ErrorOut"], { status: 401 });
    const digest = new URL(request.url).searchParams.get("digest") === "true";
    return HttpResponse.json(updates(digest) satisfies S["UpdatesOut"]);
  }),
  http.post(`${A}/me/updates/seen`, () => {
    if (!loggedIn()) return HttpResponse.json({ detail: "Log in to continue." } satisfies S["ErrorOut"], { status: 401 });
    seen = true;
    return HttpResponse.json({ thread: 1, reply: 2, post: 7, comment: 0 } satisfies S["UpdatesSeen"]);
  }),
];
