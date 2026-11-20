import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { TypeHero } from "@/components/brand/TypeHero";
import { EmptyState } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { ArrowIcon, SearchIcon } from "@/components/ui/icons";
import { controlClass } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/misc";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { SORTS, useThreadPage, useThreads, type CourseRef, type ListFilters, type Sort, type ThreadSummary } from "@/features/commons/api";
import { CourseSearch } from "@/features/commons/CourseSearch";
import { ArchGlyph, useToast } from "@/features/commons/parts";
import { ThreadCard, ThreadCardSkeleton } from "@/features/commons/ThreadCard";
import { coursePath, plural } from "@/features/commons/text";

const SORT_KEYS = new Set<string>(SORTS.map((s) => s.key));

/** The search box keeps its own text and writes `q` to the URL a moment after typing stops. */
function useDebounced<T>(value: T, ms: number): T {
  const [out, setOut] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setOut(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return out;
}

function AskBox() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    const t = title.trim();
    navigate(t ? `/forum/new?title=${encodeURIComponent(t)}` : "/forum/new");
  }
  return (
    <form onSubmit={submit} role="search" aria-label="Ask a question" className="flex flex-col gap-3">
      <label htmlFor="commons-ask" className="sr-only">
        Your question
      </label>
      <div className="flex min-w-0 items-center gap-2 rounded-pill border border-hairline-strong bg-surface-card p-1.5 pl-5 shadow-overlay focus-within:border-primary focus-within:shadow-[0_0_0_1px_var(--color-primary),0_8px_32px_rgba(0,0,0,0.08)]">
        <input
          id="commons-ask"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={160}
          autoComplete="off"
          placeholder="Is CMSC 14100 OK with no programming background?"
          className="min-h-11 min-w-0 flex-1 bg-transparent text-body-md text-ink placeholder:text-muted focus:outline-none"
        />
        <Button type="submit" className="shrink-0">
          Ask
          <ArrowIcon />
        </Button>
      </div>
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-muted">
        <span>Anonymous handles. Quarterly AI answers first.</span>
        <Link to="/instructors" className="inline-flex min-h-11 items-center gap-1 font-medium text-primary underline-offset-4 hover:underline">
          Course reviews by instructor →
        </Link>
      </p>
    </form>
  );
}

function Rail({ popular, onCourse }: { popular: CourseRef[]; onCourse: (c: CourseRef) => void }) {
  return (
    <aside aria-label="About the Commons" className="flex flex-col gap-6 lg:sticky lg:top-24">
      <section className="relative overflow-hidden rounded-xl border border-hairline bg-surface-card p-6">
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-primary" />
        <h2 className="font-display text-display-sm text-ink">How the Commons works</h2>
        <ol className="mt-4 flex flex-col gap-4 text-body-sm text-body">
          <li className="flex gap-3">
            <span aria-hidden="true" className="font-display text-title-md italic text-primary">i.</span>
            <span>
              <strong className="font-medium text-ink">Anonymous, per question.</strong> You get a random handle on each question, like “Quiet Heron”. Nobody can link your posts across questions.
            </span>
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true" className="font-display text-title-md italic text-primary">ii.</span>
            <span>
              <strong className="font-medium text-ink">The AI answers first.</strong> Quarterly AI reads the catalog and what students say, and cites its sources. It can be wrong: check, vote and correct it.
            </span>
          </li>
          <li className="flex gap-3">
            <span aria-hidden="true" className="font-display text-title-md italic text-primary">iii.</span>
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
        <section className="rounded-xl border border-hairline bg-canvas-soft p-6">
          <h2 className="text-caption-uppercase uppercase text-muted">Popular courses</h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {popular.map((c) => (
              <li key={c.code}>
                <button
                  type="button"
                  onClick={() => onCourse(c)}
                  title={`Questions about ${c.title}`}
                  className="inline-flex min-h-11 items-center rounded-pill border border-primary/25 bg-surface-card px-3 text-caption font-semibold tabular-nums text-primary hover:bg-primary-wash"
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

export default function CommonsPage() {
  const { data: session } = useSession();
  const loggedIn = !!session;
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const sort = (SORT_KEYS.has(params.get("sort") ?? "") ? params.get("sort") : "hot") as Sort;
  const courseCode = params.get("course") ?? "";
  const subject = params.get("subject") ?? "";
  const tag = params.get("tag") ?? "";
  const mine = params.get("mine") === "1" && loggedIn;
  const [search, setSearch] = useState(params.get("q") ?? "");
  const q = useDebounced(search.trim(), 300);
  const [courseTitle, setCourseTitle] = useState<string>("");

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

  const filters: ListFilters = useMemo(
    () => ({ sort, q: q || undefined, course: courseCode || undefined, subject: subject || undefined, tag: tag || undefined, mine: mine || undefined }),
    [sort, q, courseCode, subject, tag, mine],
  );
  const list = useThreads(filters);
  const items: ThreadSummary[] = useMemo(() => list.data?.pages.flatMap((p) => p.items) ?? [], [list.data]);
  const total = list.data?.pages[0]?.total ?? 0;

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
    ? { code: courseCode, title: courseTitle || items.find((t) => t.course?.code === courseCode)?.course?.title || popularCourses.find((c) => c.code === courseCode)?.title || "" }
    : null;

  const filtered = !!(q || courseCode || subject || tag || mine);
  const tagHref = (t: string) => `/forum?${new URLSearchParams({ ...(sort !== "hot" ? { sort } : {}), tag: t }).toString()}`;

  return (
    <>
      <TypeHero
        shape="arcade"
        label="A cloister arcade drawn with the titles of real courses"
        kicker="The Commons"
        title={
          <>
            Ask the quad. <em>Someone</em> knows.
          </>
        }
        subline="Questions about courses, majors and the College, asked under a random handle. Quarterly AI writes the first answer; students take it from there."
      >
        <AskBox />
      </TypeHero>

      <div className="mx-auto w-full max-w-content px-4 pb-24 sm:px-6 lg:px-8">
        <div className="sticky top-0 z-20 -mx-4 border-b border-hairline bg-canvas/95 px-4 pb-3 pt-3 backdrop-blur supports-[backdrop-filter]:bg-canvas/85 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <div role="tablist" aria-label="Sort questions" className="-mx-1 flex max-w-full gap-0.5 overflow-x-auto px-1 [scrollbar-width:none]">
                {SORTS.map((s) => (
                  <button
                    key={s.key}
                    type="button"
                    role="tab"
                    aria-selected={sort === s.key}
                    title={s.hint}
                    onClick={() => update({ sort: s.key === "hot" ? null : s.key })}
                    className={cn(
                      "inline-flex min-h-11 shrink-0 items-center rounded-pill px-3.5 text-nav-link transition-colors",
                      sort === s.key ? "bg-ink text-on-dark" : "text-body hover:bg-surface-strong hover:text-ink",
                    )}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              {loggedIn && (
                <button
                  type="button"
                  aria-pressed={mine}
                  onClick={() => update({ mine: mine ? null : "1" })}
                  className={cn(
                    "inline-flex min-h-11 items-center gap-2 rounded-pill border px-3.5 text-nav-link transition-colors",
                    mine ? "border-primary bg-primary-wash text-primary" : "border-hairline-strong text-body hover:bg-surface-strong",
                  )}
                >
                  My questions
                </button>
              )}
            </div>
            <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,18rem)]">
              <div className="relative">
                <label htmlFor="commons-search" className="sr-only">
                  Search questions
                </label>
                <SearchIcon className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <input
                  id="commons-search"
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search questions"
                  className={cn(controlClass, "pl-9 text-body-sm pointer-coarse:text-body-md")}
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
            </div>
            {(subjects.length > 0 || tags.length > 0) && (
              <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5 [scrollbar-width:thin]" aria-label="Subjects and tags" role="group">
                {subjects.map((s) => (
                  <button
                    key={`s-${s}`}
                    type="button"
                    aria-pressed={subject === s}
                    onClick={() => update({ subject: subject === s ? null : s })}
                    className={cn(
                      "inline-flex min-h-11 shrink-0 items-center rounded-pill border px-3 text-caption font-semibold tracking-[0.04em] transition-colors",
                      subject === s ? "border-primary bg-primary text-on-primary" : "border-hairline-strong bg-surface-card text-ink hover:border-primary/50",
                    )}
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
                    className={cn(
                      "inline-flex min-h-11 shrink-0 items-center rounded-pill px-3 text-caption transition-colors",
                      tag === t ? "bg-ink text-on-dark" : "bg-surface-strong text-body hover:bg-hairline",
                    )}
                  >
                    #{t}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
          <section aria-labelledby="commons-list-title" className="min-w-0">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="commons-list-title" className="font-display text-display-sm text-ink">
                {mine ? "Your questions" : courseRef ? (
                  <>
                    Questions about <Link to={coursePath(courseRef.code)} className="text-primary underline-offset-4 hover:underline">{courseRef.code}</Link>
                  </>
                ) : filtered ? "Matching questions" : SORTS.find((s) => s.key === sort)?.label === "Hot" ? "Being asked now" : `${SORTS.find((s) => s.key === sort)?.label} questions`}
              </h2>
              <p className="text-caption text-muted" aria-live="polite">
                {list.isSuccess ? plural(total, "question") : ""}
                {filtered && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearch("");
                      setCourseTitle("");
                      setParams(sort === "hot" ? {} : { sort }, { replace: true });
                    }}
                    className="ml-3 inline-flex min-h-11 items-center font-medium text-primary underline underline-offset-2"
                  >
                    Clear filters
                  </button>
                )}
              </p>
            </div>
            {list.isLoading ? (
              <div className="flex flex-col gap-3">
                <p role="status" className="sr-only">
                  Loading questions…
                </p>
                {[0, 1, 2, 3].map((i) => (
                  <ThreadCardSkeleton key={i} />
                ))}
              </div>
            ) : list.isError ? (
              <EmptyState title="The Commons could not load">
                <ErrorText>{list.error.message}</ErrorText>
                <Button variant="outline" className="mt-2" onClick={() => void list.refetch()}>
                  Try again
                </Button>
              </EmptyState>
            ) : items.length === 0 ? (
              <EmptyState
                title={
                  courseRef
                    ? `No questions yet about ${courseRef.code}. Ask the first one.`
                    : mine
                      ? "You have not asked anything yet."
                      : q
                        ? `Nothing matches “${q}” yet. Ask it.`
                        : sort === "unanswered"
                          ? "Every question has an answer. Nice."
                          : "No questions yet. Ask the first one."
                }
                action={
                  <Button asChild>
                    <Link
                      to={`/forum/new?${new URLSearchParams({ ...(courseRef ? { course: courseRef.code } : {}), ...(q ? { title: q } : {}) }).toString()}`}
                    >
                      Ask a question
                    </Link>
                  </Button>
                }
              />
            ) : (
              <>
                <ol className="flex flex-col gap-3">
                  {items.map((t) => (
                    <li key={t.id}>
                      <ThreadCard thread={t} loggedIn={loggedIn} tagHref={tagHref} />
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
                      <ArchGlyph size={16} className="text-primary" /> That is every question{filtered ? " that matches" : ""}.
                    </p>
                  )}
                </div>
              </>
            )}
          </section>
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
      {toast.node}
    </>
  );
}
