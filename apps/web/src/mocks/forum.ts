/**
 * MSW handlers for the forum, instructors and the moderation queue (prompt 08). In-memory and
 * deliberately fake: "Fake Instructor A", pseudonyms such as "Fake Heron", posts that say they
 * are fake. Forum routes answer 401 unless the mock session is logged in, like the API.
 *
 * Posts publish at once (no check before publishing, P08-1); the seeded held post stands for one
 * an earlier version of the forum held, so the moderation queue has an item.
 * Setting sessionStorage "quarterly.mock.admin" = "1" makes the mock session an admin.
 */
import { http, HttpResponse } from "msw";
import type { components } from "@/api/schema";
import { allCourses, FAKE_INSTRUCTOR, findCourse } from "./data";

type S = components["schemas"];
type Post = S["PostOut"];
type Comment = S["CommentOut"];
const A = "*/api";

const SESSION_FLAG = "quarterly.mock.session";
export const ADMIN_FLAG = "quarterly.mock.admin";
const ME = "me";

function flag(name: string): boolean {
  try {
    return globalThis.sessionStorage?.getItem(name) === "1";
  } catch {
    return false;
  }
}
const loggedIn = () => flag(SESSION_FLAG);

function json<T>(body: T, status = 200) {
  return HttpResponse.json(body as never, { status });
}
const err = (detail: string, status: number) => json<S["ErrorOut"]>({ detail }, status);
const unauthorized = () => err("Log in to continue.", 401);
const dec = (s: unknown) => decodeURIComponent(String(s));
const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString().slice(0, 10);

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
/** Mock rendering: escaped paragraphs (the real API renders markdown and sanitizes it). */
function render(md: string): string {
  return md
    .split(/\n{2,}/)
    .map((p) => `<p>${escapeHtml(p).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>")}</p>`)
    .join("\n");
}

interface PostRec {
  post: Post;
  author: string;
}
interface CommentRec {
  comment: Comment;
  author: string;
}

let posts: PostRec[] = [];
let suspensions: S["SuspensionOut"][] = [];
let comments: CommentRec[] = [];
let votes = new Map<string, number>(); // `${type}:${id}:${voter}` -> ±1
let reports: { id: number; target_type: "post" | "comment"; target_id: number; reason: string; status: string; from: string }[] = [];
let seq = 0;
const next = () => ++seq;

const PSEUDONYMS: Record<string, string> = { [ME]: "Fake Wren", a: "Fake Heron", b: "Fake Otter", c: "Fake Lark", d: "Fake Badger" };

/** Pages: one per mock course, all with Fake Instructor A (as the mock course page lists). */
function pageOf(id: number) {
  const course = allCourses()[id - 1];
  return course ? { id, course } : undefined;
}
function pageFor(code: string, slug: string) {
  const course = findCourse(code);
  if (!course || slug !== FAKE_INSTRUCTOR.slug) return undefined;
  return pageOf(allCourses().indexOf(course) + 1);
}

function addPost(pageId: number, author: string, init: Partial<Post> & Pick<Post, "kind" | "body_md">, created = today()): PostRec {
  const id = next();
  const rec: PostRec = {
    author,
    post: {
      id,
      page_id: pageId,
      pseudonym: PSEUDONYMS[author] ?? "Fake Moth",
      title: null,
      body_html: render(init.body_md),
      term_taken: null,
      score: 0,
      my_vote: 0,
      status: "visible",
      created_day: created,
      edited_day: null,
      ratings: null,
      n_comments: 0,
      mine: false,
      moderation_note: null,
      ...init,
    },
  };
  posts.push(rec);
  return rec;
}

function addComment(postId: number, author: string, body: string, parent: number | null, created = today()): CommentRec {
  const parentRec = comments.find((c) => c.comment.id === parent);
  const rec: CommentRec = {
    author,
    comment: {
      id: next(),
      post_id: postId,
      parent_id: parent,
      depth: parentRec ? parentRec.comment.depth + 1 : 0,
      pseudonym: PSEUDONYMS[author] ?? "Fake Moth",
      body_md: body,
      body_html: render(body),
      score: 0,
      my_vote: 0,
      status: "visible",
      created_day: created,
      mine: false,
      moderation_note: null,
    },
  };
  comments.push(rec);
  return rec;
}

function seed() {
  posts = [];
  comments = [];
  votes = new Map();
  reports = [];
  seq = 0;
  const ratings = (overall: number, difficulty: number, workload: number, recommend: boolean): S["ReviewRatingIn"] => ({
    overall,
    difficulty,
    intellectual_intensity: 3,
    workload_hours: workload,
    would_recommend: recommend,
    grade_bucket: null,
  });
  const r1 = addPost(1, "a", { kind: "review", body_md: "Fake review: clear lectures, weekly **problem sets**.", term_taken: "2099-AU", ratings: ratings(5, 3, 9, true) }, daysAgo(20));
  r1.post.score = 4;
  addPost(1, "b", { kind: "review", body_md: "Fake review: the pace was slow at first.", term_taken: "2099-AU", ratings: ratings(3, 2, 7, false) }, daysAgo(3));
  const d = addPost(1, "c", { kind: "discussion", title: "Fake question: is the midterm curved?", body_md: "Asking for the fake midterm." }, daysAgo(1));
  // A reply chain nine levels deep, so the thread view folds it below depth 6.
  let parent: number | null = null;
  for (let depth = 0; depth < 9; depth += 1) {
    parent = addComment(d.post.id, depth % 2 ? "a" : "b", `Fake reply at depth ${depth}.`, parent).comment.id;
  }
  addComment(d.post.id, "d", "Fake second top-level reply.", null);
  // Held for review (another author), so the moderation queue has an item.
  addPost(1, "d", { kind: "discussion", title: "Fake held post", body_md: "Fake: [hold] mentions someone.", status: "held" }, daysAgo(2));
}
seed();

export function resetForumMock() {
  suspensions = [];
  seed();
}

// ------------------------------------------------------------------------------- read models

function counts(type: "post" | "comment", id: number) {
  let up = 0;
  let down = 0;
  for (const [key, v] of votes) {
    if (key.startsWith(`${type}:${id}:`)) {
      if (v > 0) up += 1;
      else down += 1;
    }
  }
  return { up, down };
}
function wilson(up: number, down: number): number {
  const n = up + down;
  if (!n) return 0;
  const z = 1.96;
  const p = up / n;
  return (p + (z * z) / (2 * n) - z * Math.sqrt((p * (1 - p) + (z * z) / (4 * n)) / n)) / (1 + (z * z) / n);
}

function shown(rec: PostRec): Post {
  const mine = rec.author === ME;
  const visibleComments = comments.filter((c) => c.comment.post_id === rec.post.id && c.comment.status === "visible").length;
  return {
    ...rec.post,
    mine,
    my_vote: (votes.get(`post:${rec.post.id}:${ME}`) ?? 0) as Post["my_vote"],
    n_comments: visibleComments,
    moderation_note: mine ? rec.post.moderation_note : null,
  };
}

function ratingsOf(pageIds: number[]): { summary: S["RatingSummary"]; distribution: Record<string, number[]> } {
  const reviews = posts.filter((p) => pageIds.includes(p.post.page_id) && p.post.kind === "review" && p.post.status === "visible" && p.post.ratings);
  const rs = reviews.map((p) => p.post.ratings as S["ReviewRatingIn"]);
  const avg = (f: (r: S["ReviewRatingIn"]) => number) => (rs.length ? Math.round((rs.reduce((a, r) => a + f(r), 0) / rs.length) * 100) / 100 : null);
  const distribution: Record<string, number[]> = {};
  for (const key of ["overall", "difficulty", "intellectual_intensity"] as const) {
    const c = [0, 0, 0, 0, 0];
    for (const r of rs) c[r[key] - 1] = (c[r[key] - 1] ?? 0) + 1;
    distribution[key] = c;
  }
  return {
    summary: {
      n_reviews: rs.length,
      overall: avg((r) => r.overall),
      difficulty: avg((r) => r.difficulty),
      intellectual_intensity: avg((r) => r.intellectual_intensity),
      workload_hours: avg((r) => r.workload_hours),
      recommend_rate: avg((r) => (r.would_recommend ? 1 : 0)),
    },
    distribution,
  };
}

function forumPage(id: number): S["ForumPageOut"] | undefined {
  const page = pageOf(id);
  if (!page) return undefined;
  const { summary, distribution } = ratingsOf([id]);
  return {
    id,
    course_code: page.course.code,
    course_title: page.course.title,
    also_listed_as: [],
    instructor: FAKE_INSTRUCTOR,
    terms_taught: ["2099-AU", "2100-WI"],
    n_reviews: summary.n_reviews ?? 0,
    rating_distribution: distribution,
    ratings: summary,
    summary: null,
  };
}

function sortPosts(list: PostRec[], sort: string): PostRec[] {
  const key = (r: PostRec): number => {
    const { up, down } = counts("post", r.post.id);
    if (sort === "top" || sort === "hot") return r.post.score;
    if (sort === "controversial") return up && down ? (up + down) ** (Math.min(up, down) / Math.max(up, down)) : 0;
    if (sort === "new") return r.post.id;
    return wilson(up, down) + r.post.score / 1000; // seeded scores have no vote rows
  };
  return [...list].sort((a, b) => key(b) - key(a) || b.post.id - a.post.id);
}

function threadComments(postId: number): Comment[] {
  const all = comments.filter((c) => c.comment.post_id === postId && (c.comment.status === "visible" || c.author === ME));
  const out: Comment[] = [];
  const walk = (parent: number | null) => {
    const kids = all
      .filter((c) => c.comment.parent_id === parent)
      .sort((a, b) => b.comment.score - a.comment.score || b.comment.id - a.comment.id);
    for (const c of kids) {
      out.push({ ...c.comment, mine: c.author === ME, my_vote: (votes.get(`comment:${c.comment.id}:${ME}`) ?? 0) as Comment["my_vote"] });
      walk(c.comment.id);
    }
  };
  walk(null);
  return out;
}

/** Posts and comments publish at once (P08-1): no check before publishing. */
function published(): { status: Post["status"]; note: string | null } {
  return { status: "visible", note: null };
}

// ----------------------------------------------------------------------------------- handlers

export const forumHandlers = [
  http.get(`${A}/auth/session`, () => {
    if (loggedIn() && flag(ADMIN_FLAG)) {
      return json<S["SessionOut"]>({
        account: { id: "00000000-0000-4000-8000-000000000001", username: "fake-admin", role: "admin", created_day: "2099-01-01" },
        csrf_token: "fake-csrf",
      });
    }
    return undefined; // the shared mock session in handlers.ts answers
  }),

  http.get(`${A}/instructors`, ({ request }) => {
    const q = (new URL(request.url).searchParams.get("q") ?? "").toLowerCase();
    const items = [FAKE_INSTRUCTOR].filter((i) => !q || i.display_name.toLowerCase().includes(q));
    return json<S["Page_InstructorSummary_"]>({ items, total: items.length, limit: 100, offset: 0 });
  }),
  http.get(`${A}/instructors/:slug`, ({ params }) => {
    if (dec(params.slug) !== FAKE_INSTRUCTOR.slug) return err("Instructor not found", 404);
    const courses = allCourses()
      .slice(0, 2)
      .map((c, i) => ({ code: c.code, title: c.title, n_terms: 2, page_id: i + 1, attributes: [], ratings: loggedIn() ? ratingsOf([i + 1]).summary : null }));
    return json<S["InstructorDetail"]>({ ...FAKE_INSTRUCTOR, courses });
  }),

  http.get(`${A}/forum/pages`, ({ request }) => {
    if (!loggedIn()) return unauthorized();
    const u = new URL(request.url);
    const page = pageFor(u.searchParams.get("course") ?? "", u.searchParams.get("instructor") ?? "");
    const out = page ? forumPage(page.id) : undefined;
    return out ? json<S["ForumPageOut"]>(out) : err("No forum page", 404);
  }),
  http.get(`${A}/forum/pages/:id`, ({ params }) => {
    if (!loggedIn()) return unauthorized();
    const page = forumPage(Number(params.id));
    return page ? json<S["ForumPageOut"]>(page) : err("No forum page", 404);
  }),
  http.get(`${A}/forum/courses/:code`, ({ params }) => {
    if (!loggedIn()) return unauthorized();
    const course = findCourse(dec(params.code));
    if (!course) return err("No course", 404);
    const id = allCourses().indexOf(course) + 1;
    const r = ratingsOf([id]);
    return json<S["CourseForumOut"]>({
      course_code: course.code,
      course_title: course.title,
      ratings: r.summary,
      rating_distribution: r.distribution,
      pages: [{ page_id: id, instructor: FAKE_INSTRUCTOR, terms_taught: ["2099-AU"], ratings: r.summary }],
    });
  }),
  http.get(`${A}/forum/pages/:id/posts`, ({ params, request }) => {
    if (!loggedIn()) return unauthorized();
    const u = new URL(request.url);
    const kind = u.searchParams.get("kind");
    const term = u.searchParams.get("term");
    const limit = Number(u.searchParams.get("limit") ?? 20);
    const offset = Number(u.searchParams.get("offset") ?? 0);
    const list = posts.filter(
      (p) =>
        p.post.page_id === Number(params.id) &&
        (p.post.status === "visible" || p.author === ME) &&
        (!kind || p.post.kind === kind) &&
        (!term || p.post.term_taken === term),
    );
    const sorted = sortPosts(list, u.searchParams.get("sort") ?? "best");
    return json<S["Page_PostOut_"]>({ items: sorted.slice(offset, offset + limit).map(shown), total: list.length, limit, offset });
  }),
  http.post(`${A}/forum/pages/:id/posts`, async ({ params, request }) => {
    if (!loggedIn()) return unauthorized();
    const pageId = Number(params.id);
    const body = (await request.json()) as S["PostCreate"];
    if (body.kind === "review" && posts.some((p) => p.post.page_id === pageId && p.author === ME && p.post.kind === "review")) {
      return err("You have already reviewed this course with this instructor. Edit your review instead.", 409);
    }
    const m = published();
    const rec = addPost(pageId, ME, {
      kind: body.kind,
      title: body.title ?? null,
      body_md: body.body_md,
      term_taken: body.term_taken ?? null,
      ratings: body.ratings ? { ...body.ratings, grade_bucket: body.ratings.grade_bucket ?? null } : null,
      status: m.status,
      moderation_note: m.note,
    });
    return json<S["PostOut"]>(shown(rec), 201);
  }),
  http.get(`${A}/forum/posts/:id`, ({ params }) => {
    if (!loggedIn()) return unauthorized();
    const rec = posts.find((p) => p.post.id === Number(params.id));
    if (!rec || (rec.post.status !== "visible" && rec.author !== ME)) return err("Post not found.", 404);
    return json<S["PostDetail"]>({ ...shown(rec), comments: threadComments(rec.post.id) });
  }),
  http.patch(`${A}/forum/posts/:id`, async ({ params, request }) => {
    const rec = posts.find((p) => p.post.id === Number(params.id));
    if (!rec) return err("Post not found.", 404);
    if (rec.author !== ME) return err("You can only change your own posts.", 403);
    const body = (await request.json()) as S["PostUpdate"];
    if (body.body_md != null) {
      rec.post.body_md = body.body_md;
      rec.post.body_html = render(body.body_md);
    }
    if (body.title !== undefined && rec.post.kind === "discussion") rec.post.title = body.title;
    if (body.ratings) rec.post.ratings = { ...body.ratings, grade_bucket: body.ratings.grade_bucket ?? null };
    if (body.term_taken) rec.post.term_taken = body.term_taken;
    const m = published();
    rec.post.status = m.status;
    rec.post.moderation_note = m.note;
    rec.post.edited_day = today();
    return json<S["PostOut"]>(shown(rec));
  }),
  http.delete(`${A}/forum/posts/:id`, ({ params }) => {
    const rec = posts.find((p) => p.post.id === Number(params.id));
    if (!rec) return err("Post not found.", 404);
    if (rec.author !== ME) return err("You can only change your own posts.", 403);
    posts = posts.filter((p) => p !== rec);
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(`${A}/forum/posts/:id/comments`, async ({ params, request }) => {
    if (!loggedIn()) return unauthorized();
    const rec = posts.find((p) => p.post.id === Number(params.id));
    if (!rec || rec.post.status !== "visible") return err("Post not found.", 404);
    const body = (await request.json()) as S["CommentCreate"];
    const c = addComment(rec.post.id, ME, body.body_md, body.parent_id ?? null);
    const m = published();
    c.comment.status = m.status;
    c.comment.moderation_note = m.note;
    return json<S["CommentOut"]>({ ...c.comment, mine: true }, 201);
  }),
  http.post(`${A}/forum/votes`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    const body = (await request.json()) as S["VoteIn"];
    const target =
      body.target_type === "post"
        ? posts.find((p) => p.post.id === body.target_id)?.post
        : comments.find((c) => c.comment.id === body.target_id)?.comment;
    if (!target) return err("Not found.", 404);
    const key = `${body.target_type}:${body.target_id}:${ME}`;
    const before = votes.get(key) ?? 0;
    if (body.value === 0) votes.delete(key);
    else votes.set(key, body.value);
    target.score += body.value - before;
    return json<S["VoteOut"]>({ score: target.score, my_vote: body.value });
  }),
  http.post(`${A}/forum/reports`, async ({ request }) => {
    if (!loggedIn()) return unauthorized();
    const body = (await request.json()) as S["ForumReportIn"];
    const id = next();
    reports.push({ id, ...body, status: "open", from: ME });
    return json<S["ForumReportOut"]>({ id, status: "open" }, 202);
  }),

  http.get(`${A}/admin/moderation`, () => {
    if (!loggedIn()) return unauthorized();
    if (!flag(ADMIN_FLAG)) return err("Only admins can use the moderation queue.", 403);
    const targets = new Set<string>([
      ...posts.filter((p) => p.post.status === "held").map((p) => `post:${p.post.id}`),
      ...reports.filter((r) => r.status === "open").map((r) => `${r.target_type}:${r.target_id}`),
    ]);
    const items: S["ModerationItemOut"][] = [];
    for (const t of targets) {
      const [type, raw] = t.split(":");
      const id = Number(raw);
      const p = type === "post" ? posts.find((x) => x.post.id === id) : undefined;
      const c = type === "comment" ? comments.find((x) => x.comment.id === id) : undefined;
      const parent = p ?? posts.find((x) => x.post.id === c?.comment.post_id);
      if (!parent) continue;
      const page = pageOf(parent.post.page_id);
      items.push({
        target_type: type as "post" | "comment",
        target_id: id,
        post_id: parent.post.id,
        page_id: parent.post.page_id,
        course_code: page?.course.code ?? "",
        instructor_name: FAKE_INSTRUCTOR.display_name,
        instructor_slug: FAKE_INSTRUCTOR.slug,
        kind: p ? p.post.kind : "comment",
        pseudonym: (p?.post.pseudonym ?? c?.comment.pseudonym) as string,
        title: p?.post.title ?? null,
        body_md: (p?.post.body_md ?? c?.comment.body_md) as string,
        body_html: (p?.post.body_html ?? c?.comment.body_html) as string,
        status: (p?.post.status ?? c?.comment.status) as Post["status"],
        created_day: (p?.post.created_day ?? c?.comment.created_day) as string,
        model_label: p?.post.status === "held" ? "identifying_info" : null,
        reports: reports
          .filter((r) => r.status === "open" && r.target_type === type && r.target_id === id)
          .map((r) => ({ id: r.id, reason: r.reason, created_day: today(), from_author: false })),
      });
    }
    return json<S["Page_ModerationItemOut_"]>({ items, total: items.length, limit: 100, offset: 0 });
  }),
  http.post(`${A}/admin/moderation/:type/:id/decision`, async ({ params, request }) => {
    if (!flag(ADMIN_FLAG)) return err("Only admins can use the moderation queue.", 403);
    const body = (await request.json()) as S["ModerationDecision"];
    const type = String(params.type) as "post" | "comment";
    const id = Number(params.id);
    const target = type === "post" ? posts.find((p) => p.post.id === id)?.post : comments.find((c) => c.comment.id === id)?.comment;
    if (!target) return err("Not found.", 404);
    target.status = body.decision === "approve" ? "visible" : "removed";
    for (const r of reports) if (r.target_type === type && r.target_id === id && r.status === "open") r.status = body.decision === "approve" ? "dismissed" : "upheld";
    if (body.decision === "approve" && body.suspend_days) return err("A suspension goes with removing the post or comment.", 422);
    const suspended = body.decision === "remove" && !!body.suspend_days;
    if (suspended && body.suspend_days) {
      const title = type === "post" ? (target as Post).title ?? null : null;
      const until = new Date(Date.now() + body.suspend_days * 86_400_000).toISOString().slice(0, 10);
      suspensions = [
        { target_type: type, target_id: id, course_code: "TEST 10000", instructor_name: FAKE_INSTRUCTOR.display_name, title, excerpt: target.body_md.slice(0, 120), removed_day: new Date().toISOString().slice(0, 10), until },
        ...suspensions,
      ];
    }
    return json<S["ModerationResult"]>({ target_type: type, target_id: id, status: target.status, author_suspended: suspended });
  }),
  http.get(`${A}/admin/moderation/suspensions`, () => {
    if (!flag(ADMIN_FLAG)) return err("Only admins can use the moderation queue.", 403);
    return json<S["SuspensionOut"][]>(suspensions);
  }),
  http.post(`${A}/admin/moderation/:type/:id/end-suspension`, ({ params }) => {
    if (!flag(ADMIN_FLAG)) return err("Only admins can use the moderation queue.", 403);
    const type = String(params.type) as "post" | "comment";
    const id = Number(params.id);
    const before = suspensions.length;
    suspensions = suspensions.filter((s) => !(s.target_type === type && s.target_id === id));
    if (suspensions.length === before) return err("No active suspension for this item.", 404);
    return json<S["EndSuspensionResult"]>({ target_type: type, target_id: id, ended: true });
  }),
];
