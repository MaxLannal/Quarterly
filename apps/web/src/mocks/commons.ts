/**
 * MSW handlers for the campus companion's "commons" endpoints (docs/BEST-OF-UCHICAGO-PLAN.md).
 * In-memory and deliberately fake: the fake catalog's courses (TEST 10000), handles such as
 * "Fake Heron", questions that say they are fake. Reading is public like the API; writing answers
 * 401 unless the mock session is logged in. The bot streams two steps and an answer, no model.
 */
import { http, HttpResponse } from "msw";
import type { components } from "@/api/schema";

type S = components["schemas"];
type Thread = S["CommonsThreadDetail"];
type Reply = S["CommonsReply"];
type BotEvent = S["CommonsBotEvent"];
const A = "*/api";

const SESSION_FLAG = "quarterly.mock.session";
function loggedIn(): boolean {
  try {
    return globalThis.sessionStorage?.getItem(SESSION_FLAG) === "1";
  } catch {
    return false;
  }
}

function json<T>(body: T, status = 200) {
  return HttpResponse.json(body as never, { status });
}
const err = (detail: string, status: number) => json<S["ErrorOut"]>({ detail }, status);
const unauthorized = () => err("Log in to continue.", 401);
const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString().slice(0, 10);
const COURSES: Record<string, string> = { "TEST 10000": "Fake Introduction I", "TEST 20000": "Fake Theory", "FAKE 11000": "Fake Humanities I" };

let seq = 100;
let threads: Thread[] = [];
const votes = new Map<string, -1 | 0 | 1>();

function reply(id: number, body: string, extra: Partial<Reply> = {}): Reply {
  return {
    id,
    parent_id: null,
    depth: 0,
    kind: "human",
    handle: "Fake Heron",
    is_op: false,
    is_mine: false,
    body_html: `<p>${body}</p>`,
    body_md: null,
    citations: [],
    score: 0,
    my_vote: 0,
    accepted: false,
    status: "visible",
    created_day: daysAgo(1),
    edited_day: null,
    children: [],
    ...extra,
  };
}

function seed(): Thread[] {
  const base = {
    excerpt: "",
    tags: [] as string[],
    score: 0,
    reply_count: 0,
    answer_count: 0,
    answered: false,
    accepted: false,
    bot_state: "pending" as const,
    has_bot_answer: false,
    handle: "Fake Wren",
    is_mine: false,
    my_vote: 0 as const,
    status: "visible" as const,
    edited_day: null,
    body_md: null,
    mentions: [] as S["CommonsCourse"][],
    following: false,
    accepted_reply_id: null,
    last_reply_id: null,
    replies: [] as Reply[],
  };
  const answered: Thread = {
    ...base,
    id: 1,
    title: "Fake question: is TEST 10000 fine without background?",
    excerpt: "Fake data for the mock Commons.",
    body_html: "<p>Fake data for the mock Commons.</p>",
    course: { code: "TEST 10000", title: COURSES["TEST 10000"] as string },
    tags: ["first-year"],
    score: 4,
    reply_count: 2,
    answer_count: 1,
    answered: true,
    bot_state: "answered",
    has_bot_answer: true,
    created_day: daysAgo(3),
    last_reply_id: 3,
    replies: [
      reply(1, "Fake AI answer: TEST 10000 has no prerequisite.", {
        kind: "bot",
        handle: "Quarterly AI",
        citations: [{ kind: "course", id: "TEST 10000", label: "TEST 10000 · Fake Introduction I", url: "/courses/TEST%2010000" }],
      }),
      reply(2, "Fake reply: have you read the course page?", { children: [reply(3, "Fake nested reply.", { parent_id: 2, depth: 1, handle: "Fake Wren", is_op: true })] }),
    ],
  };
  const pending: Thread = {
    ...base,
    id: 2,
    title: "Fake question: which fake humanities sequence is discussion-heavy?",
    excerpt: "",
    body_html: "",
    course: { code: "FAKE 11000", title: COURSES["FAKE 11000"] as string },
    tags: ["core"],
    created_day: daysAgo(1),
  };
  return [answered, pending];
}

export function resetCommonsMock() {
  threads = seed();
  votes.clear();
  seq = 100;
}
resetCommonsMock();

function summary(t: Thread): S["CommonsThreadSummary"] {
  return {
    id: t.id,
    title: t.title,
    excerpt: t.excerpt,
    course: t.course,
    tags: t.tags,
    score: t.score,
    reply_count: t.reply_count,
    answer_count: t.answer_count,
    answered: t.answered,
    accepted: t.accepted,
    bot_state: t.bot_state,
    has_bot_answer: t.has_bot_answer,
    handle: t.handle,
    is_mine: t.is_mine,
    my_vote: t.my_vote,
    status: t.status,
    created_day: t.created_day,
    edited_day: t.edited_day,
  };
}

/** The Commons side of the `/forum` list (issue #20; the list itself is in forum.ts). */
export function discussionItems(): S["ForumDiscussionItem"][] {
  return threads
    .filter((t) => t.status === "visible")
    .map((t) => ({
      type: "discussion" as const,
      thread: summary(t),
      ai_answer_html: t.replies.find((r) => r.kind === "bot" && r.parent_id == null && r.status === "visible")?.body_html ?? null,
    }));
}

function find(id: number): Thread | undefined {
  return threads.find((t) => t.id === id && t.status === "visible");
}

function all(replies: Reply[]): Reply[] {
  return replies.flatMap((r) => [r, ...all(r.children)]);
}

function recount(t: Thread) {
  const humans = all(t.replies).filter((r) => r.kind === "human" && r.status === "visible");
  t.reply_count = humans.length;
  t.answer_count = t.replies.filter((r) => r.kind === "human" && r.status === "visible").length;
  t.answered = t.accepted_reply_id != null || t.answer_count > 0;
  t.has_bot_answer = t.replies.some((r) => r.kind === "bot");
}

function sse(events: BotEvent[]) {
  const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  return new HttpResponse(body, { headers: { "Content-Type": "text/event-stream" } });
}

const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export const commonsHandlers = [
  // The admin's Commons reports (OPEN_QUESTIONS CC-7): none in the mock world.
  http.get(`${A}/admin/commons-reports`, () => HttpResponse.json([] as S["CommonsModerationItem"][])),
  http.get(`${A}/commons/threads`, ({ request }) => {
    const u = new URL(request.url);
    const q = (u.searchParams.get("q") ?? "").toLowerCase();
    const course = u.searchParams.get("course");
    const tag = u.searchParams.get("tag");
    const sort = u.searchParams.get("sort") ?? "hot";
    if (u.searchParams.get("mine") === "true" && !loggedIn()) return unauthorized();
    let items = threads.filter((t) => t.status === "visible");
    if (q) items = items.filter((t) => `${t.title} ${t.excerpt}`.toLowerCase().includes(q));
    if (course) items = items.filter((t) => t.course?.code.replace(" ", "") === course.replace(/\s/g, "").toUpperCase());
    if (tag) items = items.filter((t) => t.tags.includes(tag));
    if (u.searchParams.get("mine") === "true") items = items.filter((t) => t.is_mine);
    if (sort === "unanswered") items = items.filter((t) => !t.answered);
    items = [...items].sort((a, b) => (sort === "top" ? b.score - a.score : b.id - a.id));
    return json<S["CommonsThreadList"]>({ items: items.map(summary), next_cursor: null, total: items.length });
  }),

  http.post(`${A}/commons/threads`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    const body = (await request.json()) as S["CommonsThreadCreate"];
    if (!body.title || body.title.trim().length < 8) return err("the title needs at least 8 characters", 422);
    const code = body.course_code?.toUpperCase() ?? null;
    if (code && !COURSES[code]) return err(`There is no course ${code}.`, 422);
    seq += 1;
    const thread: Thread = {
      ...threads[1]!,
      id: seq,
      title: body.title.trim(),
      excerpt: (body.body_md ?? "").slice(0, 200),
      body_html: body.body_md ? `<p>${escapeHtml(body.body_md)}</p>` : "",
      body_md: body.body_md ?? "",
      course: code ? { code, title: COURSES[code] as string } : null,
      tags: body.tags ?? [],
      handle: "Fake Otter",
      is_mine: true,
      score: 0,
      created_day: today(),
      replies: [],
      bot_state: "pending",
    };
    recount(thread);
    threads.unshift(thread);
    return json(thread, 201);
  }),

  http.get(`${A}/commons/threads/:id`, ({ params }) => {
    const t = find(Number(params.id));
    return t ? json(t) : err("Question not found.", 404);
  }),

  http.patch(`${A}/commons/threads/:id`, async ({ params, request }) => {
    if (!loggedIn()) return unauthorized();
    const t = find(Number(params.id));
    if (!t) return err("Question not found.", 404);
    if (!t.is_mine) return err("You can only change your own question.", 403);
    const body = (await request.json()) as S["CommonsThreadUpdate"];
    if (body.title) t.title = body.title;
    if (body.body_md != null) {
      t.body_md = body.body_md;
      t.body_html = `<p>${escapeHtml(body.body_md)}</p>`;
    }
    if (body.tags) t.tags = body.tags;
    t.edited_day = today();
    return json(t);
  }),

  http.delete(`${A}/commons/threads/:id`, ({ params }) => {
    if (!loggedIn()) return unauthorized();
    const t = find(Number(params.id));
    if (!t) return err("Question not found.", 404);
    t.status = "deleted";
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${A}/commons/threads/:id/replies`, async ({ params, request }) => {
    if (!loggedIn()) return unauthorized();
    const t = find(Number(params.id));
    if (!t) return err("Question not found.", 404);
    const body = (await request.json()) as S["CommonsReplyCreate"];
    seq += 1;
    const parent = body.parent_id ? all(t.replies).find((r) => r.id === body.parent_id) : undefined;
    const r = reply(seq, escapeHtml(body.body_md), {
      parent_id: parent?.id ?? null,
      depth: parent ? Math.min(parent.depth + 1, 4) : 0,
      handle: t.is_mine ? t.handle : "Fake Otter",
      is_op: t.is_mine,
      is_mine: true,
      body_md: body.body_md,
      created_day: today(),
    });
    if (parent) parent.children.push(r);
    else t.replies.push(r);
    t.last_reply_id = r.id;
    recount(t);
    return json<S["CommonsReplyPosted"]>({ reply: r, summon_bot: /@(quarterly|ai)\b/i.test(body.body_md), reply_count: t.reply_count }, 201);
  }),

  http.patch(`${A}/commons/replies/:id`, async ({ params, request }) => {
    if (!loggedIn()) return unauthorized();
    const r = threads.flatMap((t) => all(t.replies)).find((x) => x.id === Number(params.id));
    if (!r) return err("Reply not found.", 404);
    if (!r.is_mine) return err("You can only change your own replies.", 403);
    const body = (await request.json()) as S["CommonsReplyUpdate"];
    r.body_md = body.body_md;
    r.body_html = `<p>${escapeHtml(body.body_md)}</p>`;
    r.edited_day = today();
    return json(r);
  }),

  http.delete(`${A}/commons/replies/:id`, ({ params }) => {
    if (!loggedIn()) return unauthorized();
    for (const t of threads) {
      const r = all(t.replies).find((x) => x.id === Number(params.id));
      if (r) {
        if (!r.is_mine) return err("You can only change your own replies.", 403);
        r.status = "deleted";
        r.body_html = "<p>[deleted]</p>";
        r.handle = "[deleted]";
        recount(t);
        return new HttpResponse(null, { status: 204 });
      }
    }
    return err("Reply not found.", 404);
  }),

  http.post(`${A}/commons/votes`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    const body = (await request.json()) as S["CommonsVoteIn"];
    const target =
      body.target_type === "thread"
        ? find(body.target_id)
        : threads.flatMap((t) => all(t.replies)).find((r) => r.id === body.target_id);
    if (!target) return err("Not found.", 404);
    if (target.is_mine) return err("You can't vote on your own post.", 403);
    const key = `${body.target_type}:${body.target_id}`;
    const before = votes.get(key) ?? 0;
    votes.set(key, body.value);
    target.score += body.value - before;
    target.my_vote = body.value;
    return json<S["CommonsVoteOut"]>({ score: target.score, my_vote: body.value });
  }),

  http.post(`${A}/commons/threads/:id/accept`, async ({ params, request }) => {
    if (!loggedIn()) return unauthorized();
    const t = find(Number(params.id));
    if (!t) return err("Question not found.", 404);
    if (!t.is_mine) return err("Only the person who asked can accept.", 403);
    const body = (await request.json()) as S["CommonsAcceptIn"];
    t.accepted_reply_id = body.reply_id ?? null;
    t.accepted = t.accepted_reply_id != null;
    for (const r of all(t.replies)) r.accepted = r.id === t.accepted_reply_id;
    recount(t);
    return json<S["CommonsAcceptOut"]>({ accepted_reply_id: t.accepted_reply_id });
  }),

  http.post(`${A}/commons/threads/:id/follow`, async ({ params, request }) => {
    if (!loggedIn()) return unauthorized();
    const t = find(Number(params.id));
    if (!t) return err("Question not found.", 404);
    const body = (await request.json()) as S["CommonsFollowIn"];
    t.following = body.follow;
    return json<S["CommonsFollowOut"]>({ following: body.follow });
  }),

  http.post(`${A}/commons/threads/:id/typing`, () => (loggedIn() ? new HttpResponse(null, { status: 204 }) : unauthorized())),

  http.get(`${A}/commons/threads/:id/presence`, ({ params }) => {
    const t = find(Number(params.id));
    if (!t) return err("Question not found.", 404);
    return json<S["CommonsPresence"]>({ typing: 0, latest_reply_id: t.last_reply_id, reply_count: t.reply_count, score: t.score, bot_state: t.bot_state });
  }),

  http.post(`${A}/commons/threads/:id/bot`, async ({ params, request }) => {
    const t = find(Number(params.id));
    if (!t) return err("Question not found.", 404);
    const body = (await request.json().catch(() => ({}))) as Partial<S["CommonsBotRequest"]>;
    const existing = t.replies.find((r) => r.kind === "bot");
    if (existing && !body.regenerate && !body.reply_to) return sse([{ type: "answer", reply: existing, fallback: false }, { type: "done" }]);
    seq += 1;
    const code = t.course?.code ?? "TEST 10000";
    const answer = reply(seq, `Fake AI answer about ${code}: read the course page first.`, {
      kind: "bot",
      handle: "Quarterly AI",
      parent_id: body.reply_to ?? null,
      depth: body.reply_to ? 1 : 0,
      created_day: today(),
      citations: [{ kind: "course", id: code, label: `${code} · ${COURSES[code] ?? "Fake course"}`, url: `/courses/${encodeURIComponent(code)}` }],
    });
    if (body.reply_to) all(t.replies).find((r) => r.id === body.reply_to)?.children.push(answer);
    else t.replies.unshift(answer);
    t.bot_state = "answered";
    t.last_reply_id = answer.id;
    recount(t);
    return sse([
      { type: "step", tool: "get_course", label: `Reading ${code}`, status: "started" },
      { type: "step", tool: "get_course", label: `Reading ${code}`, status: "done" },
      { type: "step", tool: "search_commons", label: "Searching forum questions", status: "started" },
      { type: "step", tool: "search_commons", label: "Searching forum questions", status: "done" },
      { type: "answer", reply: answer, fallback: false },
      { type: "done" },
    ]);
  }),

  http.post(`${A}/commons/reports`, () => (loggedIn() ? json<S["CommonsReportOut"]>({ id: 1, status: "open" }, 202) : unauthorized())),
];
