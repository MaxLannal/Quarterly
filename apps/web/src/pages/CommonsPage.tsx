import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { TypeHero } from "@/components/brand/TypeHero";
import "@/features/courses/glass.css";
import { EmptyState } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { SearchIcon } from "@/components/ui/icons";
import { controlClass } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/misc";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { itemKey, TYPES, useForumItems, type ItemFilters, type ItemType } from "@/features/board/api";
import { InstructorSearch } from "@/features/board/InstructorSearch";
import { ReviewCard } from "@/features/board/ReviewCard";
import { StatsPanel } from "@/features/board/StatsPanel";
import { useThreadPage, type CourseRef } from "@/features/commons/api";
import { CourseSearch } from "@/features/commons/CourseSearch";
import { ArchGlyph, LoginCard, useToast } from "@/features/commons/parts";
import { ThreadCard, ThreadCardSkeleton } from "@/features/commons/ThreadCard";
import { coursePath, plural } from "@/features/commons/text";
import type { InstructorSummary } from "@/features/forum/api";

/** The search box keeps its own text and writes `q` to the URL a moment after typing stops. */
function useDebounced<T>(value: T, ms: number): T {
  const [out, setOut] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setOut(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return out;
}

/** Issue #20: the forum starts discussions, not chatbot questions, so the header has a "New post" button. */
function NewPost() {
  return (
    <div className="flex flex-col items-start gap-3">
      <Button asChild>
        <Link to="/forum/new">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New post
        </Link>
      </Button>
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-muted">
        <Link to="/instructors" className="inline-flex min-h-11 items-center gap-1 font-medium text-primary underline-offset-4 hover:underline">
          Course reviews by instructor →
        </Link>
      </p>
    </div>
  );
}

function Rail({ popular, onCourse }: { popular: CourseRef[]; onCourse: (c: CourseRef) => void }) {
  return (
    <aside aria-label="About the forum" className="flex flex-col gap-6">
      <section className="qg-tile qg-edge overflow-hidden p-7">
        <h2 className="font-display text-display-sm text-ink">How the forum works</h2>
        <ol className="mt-4 flex flex-col gap-4 text-body-sm text-body">
          <li className="flex gap-3">
            <span aria-hidden="true" className="w-6 shrink-0 font-display text-[26px] italic leading-none text-primary [text-shadow:0_0_18px_rgb(255_92_112/0.6)]">i.</span>
            <span>
              <strong className="font-medium text-ink">Anonymous, per post.</strong> You get a random handle on each question and each course page, like “Quiet Heron”. Nobody can link your posts across them.
            </span>
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true" className="w-6 shrink-0 font-display text-[26px] italic leading-none text-primary [text-shadow:0_0_18px_rgb(255_92_112/0.6)]">ii.</span>
            <span>
              <strong className="font-medium text-ink">The AI answers first, briefly.</strong> Quarterly AI writes a short first answer (60 words at most) from the catalog and earlier questions, and cites its sources. It can be wrong: check, vote and correct it.
            </span>
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true" className="w-6 shrink-0 font-display text-[26px] italic leading-none text-primary [text-shadow:0_0_18px_rgb(255_92_112/0.6)]">iii.</span>
            <span>
              <strong className="font-medium text-ink">Be kind and specific.</strong> Talk about courses, not people. Email addresses and phone numbers are removed automatically.
            </span>
          </li>
        </ol>
        <Link to="/guidelines" className="mt-4 inline-flex min-h-11 items-center text-caption font-medium text-primary underline underline-offset-2">
          Community guidelines
        </Link>
      </section>
      {popular.length > 0 && (
        <section className="qg-tile p-7">
          <h2 className="qg-kicker">Popular courses</h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {popular.map((c) => (
              <li key={c.code}>
                <button
                  type="button"
                  onClick={() => onCourse(c)}
                  title={`Posts about ${c.title}`}
                  className="qg-pill px-3.5 font-mono text-[12px] uppercase tracking-[0.12em] text-ink"
                >
                  {c.code}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}

function tally<T>(items: T[], key: (t: T) => string | null | undefined): [string, number][] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const k = key(item);
    if (k) counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

const TYPE_KEYS = new Set<string>(["review", "discussion"]);

export default function CommonsPage() {
  const { data: session } = useSession();
  const loggedIn = !!session;
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const type = (TYPE_KEYS.has(params.get("type") ?? "") ? params.get("type") : null) as ItemType | null;
  const courseCode = params.get("course") ?? "";
  const instructorSlug = params.get("instructor") ?? "";
  const subject = params.get("subject") ?? "";
  const tag = params.get("tag") ?? "";
  const mine = params.get("mine") === "1" && loggedIn;
  const [search, setSearch] = useState(params.get("q") ?? "");
  const q = useDebounced(search.trim(), 300);
  const [courseTitle, setCourseTitle] = useState<string>("");
  const [instructorName, setInstructorName] = useState<string>("");

  // A toast handed over by another page ("Question deleted").
  const handed = (location.state as { toast?: string } | null)?.toast;
  useEffect(() => {
    if (handed) {
      toast.show(handed);
      navigate(location.pathname + location.search, { replace: true, state: null });
    }
  }, [handed, toast, navigate, location.pathname, location.search]);

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next, { replace: true });
  }

  useEffect(() => {
    if ((params.get("q") ?? "") !== q) update({ q: q || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when the debounced text changes
  }, [q]);

  const filters: ItemFilters = useMemo(
    () => ({
      type: type ?? undefined,
      q: q || undefined,
      course: courseCode || undefined,
      instructor: instructorSlug || undefined,
      subject: subject || undefined,
      tag: tag || undefined,
      mine: mine || undefined,
    }),
    [type, q, courseCode, instructorSlug, subject, tag, mine],
  );
  const list = useForumItems(filters, loggedIn);
  const items = useMemo(() => list.data?.pages.flatMap((p) => p.items) ?? [], [list.data]);
  const total = list.data?.pages[0]?.total ?? 0;
  const reviewsHidden = list.data?.pages[0]?.reviews_hidden ?? !loggedIn;

  // The rail and the chips come from the whole Commons (top 30), not the filtered list.
  const overview = useThreadPage({ sort: "top" }, 30);
  const everything = useMemo(() => overview.data?.items ?? [], [overview.data]);
  const popularCourses: CourseRef[] = useMemo(() => {
    const titles = new Map(everything.filter((t) => t.course).map((t) => [t.course!.code, t.course!.title]));
    return tally(everything, (t) => t.course?.code)
      .slice(0, 10)
      .map(([code]) => ({ code, title: titles.get(code) ?? "" }));
  }, [everything]);
  const subjects = useMemo(() => tally(everything, (t) => t.course?.code.split(" ")[0]).slice(0, 8).map(([s]) => s), [everything]);
  const tags = useMemo(() => {
    const counts = new Map<string, number>();
    for (const t of everything) for (const g of t.tags) counts.set(g, (counts.get(g) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([g]) => g);
  }, [everything]);

  const courseRef: CourseRef | null = courseCode
    ? {
        code: courseCode,
        title:
          courseTitle ||
          items.map((i) => (i.type === "review" ? i.course : i.thread.course)).find((c) => c?.code === courseCode)?.title ||
          popularCourses.find((c) => c.code === courseCode)?.title ||
          "",
      }
    : null;
  const instructorRef: InstructorSummary | null = instructorSlug
    ? {
        slug: instructorSlug,
        display_name:
          instructorName || items.map((i) => (i.type === "review" ? i.instructor : null)).find((x) => x?.slug === instructorSlug)?.display_name || instructorSlug,
      }
    : null;

  const filtered = !!(type || q || courseCode || instructorSlug || subject || tag || mine);
  const tagHref = (t: string) => `/forum?${new URLSearchParams({ tag: t }).toString()}`;
  const courseHref = (code: string) => `/forum?${new URLSearchParams({ course: code }).toString()}`;
  const instructorHref = (slug: string) => `/forum?${new URLSearchParams({ instructor: slug }).toString()}`;
  const noun = type === "review" ? "review" : type === "discussion" ? "discussion" : "post";

  const heading = mine ? (
    "Your questions"
  ) : courseRef ? (
    <>
      About <Link to={coursePath(courseRef.code)} className="text-primary underline-offset-4 hover:underline">{courseRef.code}</Link>
    </>
  ) : instructorRef ? (
    `Reviews of ${instructorRef.display_name}`
  ) : filtered && !type ? (
    "Matching posts"
  ) : type === "review" ? (
    "Latest reviews"
  ) : type === "discussion" ? (
    "Latest discussions"
  ) : (
    "Latest posts"
  );

  return (
    <>
      <TypeHero
        shape="arcade"
        label="A cloister arcade drawn with the titles of real courses"
        kicker="The forum"
        title={
          <>
            Ask the quad. <em>Someone</em> knows.
          </>
        }
        subline="Course reviews and discussions, under a random handle. Quarterly AI writes a short first answer to each question; students take it from there."
      >
        <NewPost />
      </TypeHero>

      <div className="mx-auto w-full max-w-content px-4 pb-24 sm:px-6 lg:px-8">
        <div className="glass z-20 rounded-[28px] bg-[rgb(14_7_9/0.72)] p-3 sm:sticky sm:top-20 sm:p-4">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <div role="group" aria-label="Show" className="-mx-1 flex max-w-full gap-1.5 overflow-x-auto px-1 py-0.5 [scrollbar-width:none]">
                {TYPES.map((t) => (
                  <button
                    key={t.label}
                    type="button"
                    aria-pressed={type === t.key}
                    onClick={() => update({ type: t.key })}
                    className="qg-pill"
                  >
                    {type === t.key && <span aria-hidden="true" className="qg-dot" />}
                    {t.label}
                  </button>
                ))}
              </div>
              {loggedIn && (
                <button
                  type="button"
                  aria-pressed={mine}
                  onClick={() => update({ mine: mine ? null : "1" })}
                  className="qg-pill"
                >
                  My questions
                </button>
              )}
            </div>
            <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,16rem)_minmax(0,16rem)]">
              <div className="relative">
                <label htmlFor="commons-search" className="sr-only">
                  Search posts
                </label>
                <SearchIcon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-primary" />
                <input
                  id="commons-search"
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search reviews and discussions"
                  className={cn(controlClass, "pl-11 text-body-sm pointer-coarse:text-body-md")}
                />
              </div>
              <CourseSearch
                label="Filter by course"
                labelHidden
                placeholder="Filter by course"
                value={courseRef}
                onChange={(c) => {
                  setCourseTitle(c?.title ?? "");
                  update({ course: c?.code ?? null });
                }}
              />
              <InstructorSearch
                value={instructorRef}
                onChange={(i) => {
                  setInstructorName(i?.display_name ?? "");
                  update({ instructor: i?.slug ?? null });
                }}
              />
            </div>
            {(subjects.length > 0 || tags.length > 0) && (
              <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5 [scrollbar-width:thin]" aria-label="Subjects and tags" role="group">
                {subjects.map((s) => (
                  <button
                    key={`s-${s}`}
                    type="button"
                    aria-pressed={subject === s}
                    onClick={() => update({ subject: subject === s ? null : s })}
                    className="qg-pill px-3.5 font-mono text-[12px] uppercase tracking-[0.14em]"
                  >
                    {s}
                  </button>
                ))}
                {subjects.length > 0 && tags.length > 0 && <span aria-hidden="true" className="mx-1 my-3 w-px shrink-0 bg-hairline-strong" />}
                {tags.map((t) => (
                  <button
                    key={`t-${t}`}
                    type="button"
                    aria-pressed={tag === t}
                    onClick={() => update({ tag: tag === t ? null : t })}
                    className="qg-pill px-3.5 text-caption"
                  >
                    #{t}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Issue #20: statistics in the left third, the list in the right two thirds; on a phone the
            statistics come first, then the list, then the notes about the forum. */}
        <div className="mt-8 grid gap-8 lg:grid-cols-3 lg:grid-rows-[auto_1fr] lg:gap-10">
          <div className="min-w-0 lg:col-start-1 lg:row-start-1">
            <StatsPanel loggedIn={loggedIn} courseHref={courseHref} instructorHref={instructorHref} />
          </div>
          <section aria-labelledby="commons-list-title" className="min-w-0 lg:col-span-2 lg:col-start-2 lg:row-span-2 lg:row-start-1">
            <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2 border-b border-hairline pb-4">
              <h2 id="commons-list-title" className="font-display text-display-sm text-ink sm:text-display-md">
                {heading}
              </h2>
              <p className="text-caption text-muted" aria-live="polite">
                {list.isSuccess ? plural(total, noun) : ""}
                {filtered && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearch("");
                      setCourseTitle("");
                      setInstructorName("");
                      setParams({}, { replace: true });
                    }}
                    className="ml-3 inline-flex min-h-11 items-center font-medium text-primary underline underline-offset-2"
                  >
                    Clear filters
                  </button>
                )}
              </p>
            </div>
            {reviewsHidden && type !== "discussion" && !tag && !mine && (
              <LoginCard className="mb-4">
                {type === "review" || instructorSlug ? "Reviews are for logged-in students. Log in to read them." : "Showing discussions. Log in to read course reviews too."}
              </LoginCard>
            )}
            {list.isLoading ? (
              <div className="flex flex-col gap-3">
                <p role="status" className="sr-only">
                  Loading posts…
                </p>
                {[0, 1, 2, 3].map((i) => (
                  <ThreadCardSkeleton key={i} />
                ))}
              </div>
            ) : list.isError ? (
              <EmptyState title="The forum could not load">
                <ErrorText>{list.error.message}</ErrorText>
                <Button variant="outline" className="mt-2" onClick={() => void list.refetch()}>
                  Try again
                </Button>
              </EmptyState>
            ) : items.length === 0 ? (
              reviewsHidden && (type === "review" || instructorSlug) ? null : (
                <EmptyState
                  title={
                    courseRef
                      ? `Nothing yet about ${courseRef.code}. Start the first discussion.`
                      : mine
                        ? "You have not asked anything yet."
                        : q
                          ? `Nothing matches “${q}” yet. Ask it.`
                          : type === "review"
                            ? "No reviews yet."
                            : "No posts yet. Start the first discussion."
                  }
                  action={
                    <Button asChild>
                      <Link to={`/forum/new?${new URLSearchParams({ ...(courseRef ? { course: courseRef.code } : {}), ...(q ? { title: q } : {}) }).toString()}`}>New post</Link>
                    </Button>
                  }
                />
              )
            ) : (
              <>
                <ol className="flex flex-col gap-4">
                  {items.map((item) => (
                    <li key={itemKey(item)}>
                      {item.type === "review" ? (
                        <ReviewCard review={item} />
                      ) : (
                        <ThreadCard thread={item.thread} loggedIn={loggedIn} tagHref={tagHref} aiAnswerHtml={item.ai_answer_html} />
                      )}
                    </li>
                  ))}
                </ol>
                <div className="mt-6 flex flex-col items-center gap-2">
                  {list.hasNextPage ? (
                    <Button variant="outline" onClick={() => void list.fetchNextPage()} disabled={list.isFetchingNextPage}>
                      {list.isFetchingNextPage ? "Loading…" : `Load more (${total - items.length} left)`}
                    </Button>
                  ) : (
                    <p className="flex items-center gap-2 text-caption text-muted">
                      <ArchGlyph size={16} className="text-primary" /> That is every {noun}
                      {filtered ? " that matches" : ""}.
                    </p>
                  )}
                </div>
              </>
            )}
          </section>
          <div className="min-w-0 lg:col-start-1 lg:row-start-2">
            <Rail
              popular={popularCourses}
              onCourse={(c) => {
                setCourseTitle(c.title);
                update({ course: c.code });
                window.scrollTo({ top: 0 });
              }}
            />
          </div>
        </div>
      </div>
      {toast.node}
    </>
  );
}
