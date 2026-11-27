import { useId, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { isNotAvailable } from "@/api/client";
import { useCourseSearch, type CourseSearchParams } from "@/api/hooks";
import type { CourseSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { ArrowIcon, ChevronIcon, SearchIcon } from "@/components/ui/icons";
import { EmptyState, inlineLinkClass, PageContainer } from "@/components/layout/page";
import {
  Badge,
  CourseCode,
  Dots,
  ErrorText,
  NotAvailable,
  Spinner,
} from "@/components/ui/misc";
import { useAuthLinks } from "@/features/auth/next";
import { CatalogToggle } from "@/features/courses/CatalogToggle";
import { Kicker } from "@/features/courses/Glass";
import { RatingLine } from "@/features/courses/RatingLine";
import { useCatalogBrowse, useCourseRatings, type RatingSummary } from "@/features/feed/api";
import { BrowseRows, browseCodes } from "@/features/feed/BrowseRows";
import { attribute, isEstimate, round1 } from "@/features/planner/metrics";
import { useSession } from "@/lib/session";

const PAGE = 20;
const QUARTER_OPTIONS = [
  ["", "Any quarter"],
  ["AU", "Autumn"],
  ["WI", "Winter"],
  ["SP", "Spring"],
  ["SU", "Summer"],
] as const;

function paramsFrom(sp: URLSearchParams): CourseSearchParams {
  const num = (k: string) => (sp.get(k) ? Number(sp.get(k)) : undefined);
  const str = (k: string) => sp.get(k) || undefined;
  return {
    q: str("q"),
    subject: str("subject"),
    level: num("level"),
    quarter: (str("quarter") as CourseSearchParams["quarter"]) ?? undefined,
    core_tag: str("core_tag"),
    max_workload_hours: num("max_workload_hours"),
    max_difficulty: num("max_difficulty"),
    limit: PAGE,
    offset: num("offset") ?? 0,
  };
}

/**
 * A course in the results: a code plate (the subject in mono over the number in the display
 * serif), the title, the student rating line and the quiet facts. The whole tile is the link's
 * target; the link's name stays "CODE · Title".
 */
export function CourseRow({ c, rating }: { c: CourseSummary; rating?: RatingSummary }) {
  const hours = attribute(c, "workload_hours");
  const diff = attribute(c, "difficulty");
  const [subject = c.code, number = ""] = c.code.split(" ");
  return (
    <li data-spotlight="" className="qg-tile qg-tile-link group flex min-w-0 gap-4 p-4 sm:gap-5 sm:p-5">
      <span
        aria-hidden="true"
        className="flex w-[78px] shrink-0 flex-col justify-center rounded-[18px] border border-hairline bg-[linear-gradient(160deg,rgb(255_92_112/0.18),rgb(255_255_255/0.02)_62%)] px-3 py-3 shadow-[inset_0_1px_0_rgb(255_255_255/0.08)] sm:w-[92px]"
      >
        <span className="font-mono text-[10.5px] font-medium uppercase tracking-[0.18em] text-muted">{subject}</span>
        <span className="qg-numeral mt-1 text-[28px] sm:text-[32px]">{number}</span>
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <Link
          to={`/courses/${encodeURIComponent(c.code)}`}
          className="flex flex-col gap-1 rounded-xs text-ink after:absolute after:inset-0 after:rounded-[24px] hover:[&>span:last-child]:text-primary-hover"
        >
          <CourseCode className="sr-only">{c.code}</CourseCode> <span className="sr-only">·</span>{" "}
          <span className="text-title-md transition-colors duration-300">{c.title}</span>
        </Link>
        <RatingLine rating={rating} />
        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-2 pt-1 text-caption text-muted">
          <span>{c.units} units</span>
          {hours && (
            <span>
              {isEstimate(hours) ? "~" : ""}
              {round1(hours.value)} h/wk{isEstimate(hours) ? " (estimate)" : ""}
            </span>
          )}
          {diff && <Dots value={diff.value} label="Difficulty" />}
          {c.core_tags.map((t) => (
            <Badge key={t}>Core: {t}</Badge>
          ))}
          {c.crosslists.length > 0 && <span>Also {c.crosslists.join(", ")}</span>}
        </div>
      </div>
      <span
        aria-hidden="true"
        className="hidden size-11 shrink-0 items-center justify-center self-center rounded-pill border border-hairline text-muted transition-[color,border-color,translate] duration-300 group-hover:translate-x-0.5 group-hover:border-primary/50 group-hover:text-primary sm:inline-flex"
      >
        <ArrowIcon size={16} />
      </span>
    </li>
  );
}

/** A filter as a two-line glass chip: the mono label over its control. */
function FilterChip({ id, label, set, children }: { id: string; label: string; set: boolean; children: ReactNode }) {
  return (
    <div className="qg-filter" data-set={set || undefined}>
      <label htmlFor={id}>{label}</label>
      {children}
    </div>
  );
}

/**
 * The Catalog page (`/courses`, issue #19): the course search with its filters, and before the
 * student searches, the browse rows that replaced the Feed (newly released courses, course
 * spotlights, what students say). Student ratings show on every course for a logged-in student.
 *
 * Dark glass (docs/DESIGN.md): a centred command field of glass with a ring of light round its
 * edge, a mono hint line, the extra filters as two-line glass chips beneath, then editorial rows.
 */
export default function CoursesPage() {
  const [sp, setSp] = useSearchParams();
  const session = useSession();
  const authLinks = useAuthLinks();
  const account = session.data?.account ?? null;
  const loggedIn = account !== null;
  const params = paramsFrom(sp);
  const [draft, setDraft] = useState(() => Object.fromEntries(sp.entries()));
  // Results only after a search (FEEDBACK 2026-11-16: a simple, centered search); before it, the
  // browse rows (issue #19).
  const searched = [...sp.entries()].some(([k, v]) => k !== "offset" && v);
  const filtered = [...sp.entries()].some(
    ([k, v]) => k !== "offset" && k !== "q" && v,
  );
  const activeFilters = [...sp.entries()].filter(([k, v]) => k !== "offset" && k !== "q" && v).length;
  const q = useCourseSearch(params, searched);
  const browse = useCatalogBrowse(account?.id ?? "anon", !searched && !session.isLoading);
  const shown = searched ? (q.data?.items.map((c) => c.code) ?? []) : browseCodes(browse.data);
  const ratingsQuery = useCourseRatings(account?.id ?? null, shown);
  // Never show ratings logged out, not even from a cache (checklist item 9 of issue #19).
  const ratings = loggedIn ? ratingsQuery.data : undefined;
  const id = useId();
  const field = (k: string) => `${id}-${k}`;

  function submit(e: FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams();
    for (const [k, v] of Object.entries(draft))
      if (v && k !== "offset") next.set(k, v);
    setSp(next);
  }
  function page(offset: number) {
    const next = new URLSearchParams(sp);
    next.set("offset", String(offset));
    setSp(next);
  }
  const set = (k: string) => (e: { target: { value: string } }) =>
    setDraft((d) => ({ ...d, [k]: e.target.value }));
  // Keep the form in sync when the header search changes the URL.
  const urlQ = sp.get("q") ?? "";
  const [lastQ, setLastQ] = useState(urlQ);
  if (urlQ !== lastQ) {
    setLastQ(urlQ);
    setDraft((d) => ({ ...d, q: urlQ }));
  }
  const year = browse.data?.catalog_year;
  const offset = params.offset ?? 0;
  const total = q.data?.total ?? 0;

  return (
    <PageContainer>
      <div className="qg-hero mx-auto flex w-full max-w-[880px] flex-col items-center gap-6 pt-6 text-center sm:pt-14">
        <CatalogToggle current="courses" />
        <div className="flex flex-col items-center gap-3">
          <Kicker>{year ? `The catalog // ${year}` : "The catalog"}</Kicker>
          <h1 className="font-display text-display-lg text-ink [text-shadow:0_0_60px_rgb(255_92_112/0.25)] sm:text-display-mega">Catalog</h1>
          <p className="max-w-[34rem] text-body-md text-body">
            Every course, when it runs, what it leads to, and what students say about it.
          </p>
        </div>
        <form
          onSubmit={submit}
          className="mt-2 w-full text-left"
          aria-label="Course filters"
        >
          <div className="qg-command">
            <span aria-hidden="true" className="qg-command-ring">
              <span />
            </span>
            <SearchIcon size={20} className="qg-command-icon" />
            <label htmlFor={field("q")} className="sr-only">
              Code or title
            </label>
            <input
              id={field("q")}
              type="search"
              placeholder="Search by code or title"
              value={draft.q ?? ""}
              onChange={set("q")}
            />
            <Button type="submit" className="px-7">Search</Button>
          </div>
          <p aria-hidden="true" className="mt-3 text-center font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
            Try a code like <span className="text-body-strong">TEST 20000</span> <span className="px-1.5 text-muted-soft">//</span> a word from a title
          </p>
          <details className="group mt-5" open={filtered}>
            {/* D11 CS-2: a chevron shows it opens. */}
            <summary className="qg-pill mx-auto flex w-fit cursor-pointer list-none [&::-webkit-details-marker]:hidden">
              <ChevronIcon className="size-4 text-muted transition-transform duration-300 group-open:rotate-90 motion-reduce:transition-none" />
              More filters
              {activeFilters > 0 && (
                <span className="inline-flex min-w-5 items-center justify-center rounded-pill bg-primary px-1.5 text-[12px] font-semibold text-on-primary">
                  <span className="sr-only">, active: </span>
                  {activeFilters}
                </span>
              )}
            </summary>
            <div className="qg-rise mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
              <FilterChip id={field("subject")} label="Department" set={!!draft.subject}>
                <input
                  id={field("subject")}
                  placeholder="e.g. CMSC"
                  value={draft.subject ?? ""}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      subject: e.target.value.toUpperCase(),
                    }))
                  }
                />
              </FilterChip>
              <FilterChip id={field("level")} label="Level" set={!!draft.level}>
                <select
                  id={field("level")}
                  value={draft.level ?? ""}
                  onChange={set("level")}
                >
                  <option value="">Any level</option>
                  {[10000, 20000, 30000, 40000].map((l) => (
                    <option key={l} value={l}>
                      {l}s
                    </option>
                  ))}
                </select>
              </FilterChip>
              <FilterChip id={field("quarter")} label="Quarter offered" set={!!draft.quarter}>
                <select
                  id={field("quarter")}
                  value={draft.quarter ?? ""}
                  onChange={set("quarter")}
                >
                  {QUARTER_OPTIONS.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </FilterChip>
              <FilterChip id={field("core")} label="Core area" set={!!draft.core_tag}>
                <input
                  id={field("core")}
                  placeholder="e.g. arts"
                  value={draft.core_tag ?? ""}
                  onChange={set("core_tag")}
                />
              </FilterChip>
              <FilterChip id={field("hours")} label="Max hours/week" set={!!draft.max_workload_hours}>
                <input
                  id={field("hours")}
                  type="number"
                  min={0}
                  placeholder="Any"
                  value={draft.max_workload_hours ?? ""}
                  onChange={set("max_workload_hours")}
                />
              </FilterChip>
              <FilterChip id={field("diff")} label="Max difficulty" set={!!draft.max_difficulty}>
                <select
                  id={field("diff")}
                  value={draft.max_difficulty ?? ""}
                  onChange={set("max_difficulty")}
                >
                  <option value="">Any</option>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n} of 5
                    </option>
                  ))}
                </select>
              </FilterChip>
              <div className="col-span-2 flex flex-wrap items-center justify-center gap-2 pt-2 sm:col-span-3">
                <Button type="submit" variant="glow">
                  Apply filters
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setDraft({});
                    setSp(new URLSearchParams());
                  }}
                >
                  Clear
                </Button>
              </div>
            </div>
          </details>
        </form>
        {!session.isLoading && !loggedIn && (
          // Ratings need a login, as on the course page (CourseOverview).
          <p className="text-caption text-muted">
            <Link to={authLinks.login} className={inlineLinkClass}>
              Log in
            </Link>{" "}
            to see student ratings.
          </p>
        )}
      </div>

      {!searched && (
        <BrowseRows data={browse.data} isLoading={browse.isLoading} isError={browse.isError} ratings={ratings} />
      )}

      {searched && (
        <section aria-label="Results" className="mx-auto mt-14 w-full max-w-[1240px]">
          {q.isLoading ? (
            <Spinner label="Searching" />
          ) : q.error ? (
            isNotAvailable(q.error) ? (
              <NotAvailable feature="Course search" />
            ) : (
              <ErrorText>Could not load courses.</ErrorText>
            )
          ) : (
            <>
              <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-hairline pb-4">
                <p className="font-display text-display-sm text-ink" role="status">
                  {total} course{total === 1 ? "" : "s"}
                </p>
                {total > PAGE && (
                  <p className="font-mono text-[11.5px] uppercase tracking-[0.18em] text-muted">
                    {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
                  </p>
                )}
              </div>
              {total === 0 ? (
                // D11 CS-4: a way out instead of an empty list and dead paging.
                <EmptyState
                  title="No courses match"
                  className="mt-6"
                  action={
                    <Button
                      variant="outline"
                      onClick={() => {
                        setDraft({});
                        setSp(new URLSearchParams());
                      }}
                    >
                      Clear the search
                    </Button>
                  }
                >
                  Try a shorter code or title, or fewer filters.
                </EmptyState>
              ) : (
                <ul className="mt-6 grid gap-3 lg:grid-cols-2 lg:gap-4">
                  {q.data?.items.map((c) => (
                    <CourseRow key={c.code} c={c} rating={ratings?.[c.code]} />
                  ))}
                </ul>
              )}
              {/* Paging only when there is more than one page. */}
              {total > PAGE && (
                <div className="mt-10 flex justify-center gap-3">
                  <Button
                    variant="outline"
                    disabled={offset === 0}
                    onClick={() => page(Math.max(0, offset - PAGE))}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    disabled={offset + PAGE >= total}
                    onClick={() => page(offset + PAGE)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </section>
      )}
    </PageContainer>
  );
}
