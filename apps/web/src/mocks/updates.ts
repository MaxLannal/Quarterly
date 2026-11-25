/**
 * MSW handlers for `/me/updates` (logged in only) and `/me/updates/seen`. The endpoint stays
 * (issue #15 step 13), but since issue #16 (D5) removed the dashboard's "What's new" card nothing
 * in the app reads it. Fake data; no model involved. (The Ask chatbot's `/agents/ask` mock went
 * with the Ask page, issue #15.)
 */
import { http, HttpResponse } from "msw";
import type { components } from "@/api/schema";

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

let seen = false;

function updates(): S["UpdatesOut"] {
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
      reason: "About TEST 20000, a course you follow",
      is_new: false,
    },
  ];
  return { items, unread: items.filter((i) => i.is_new).length };
}

export function resetUpdatesMock() {
  seen = false;
}

export const updatesHandlers = [
  http.get(`${A}/me/updates`, () => {
    if (!loggedIn()) return HttpResponse.json({ detail: "Log in to continue." } satisfies S["ErrorOut"], { status: 401 });
    return HttpResponse.json(updates() satisfies S["UpdatesOut"]);
  }),
  http.post(`${A}/me/updates/seen`, () => {
    if (!loggedIn()) return HttpResponse.json({ detail: "Log in to continue." } satisfies S["ErrorOut"], { status: 401 });
    seen = true;
    return HttpResponse.json({ thread: 1, reply: 2, post: 7, comment: 0 } satisfies S["UpdatesSeen"]);
  }),
];
