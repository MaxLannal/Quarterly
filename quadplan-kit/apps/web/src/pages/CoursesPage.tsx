import { useId, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { isNotAvailable } from "@/api/client";
import { useCourseSearch, type CourseSearchParams } from "@/api/hooks";
import type { CourseSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { ChevronIcon } from "@/components/ui/icons";
import { EmptyState, PageContainer } from "@/components/layout/page";
import { Card } from "@/components/ui/card";
import { controlClass } from "@/components/ui/input";
import {
  Badge,
  CourseCode,
  Dots,
  ErrorText,
  NotAvailable,
  Spinner,
} from "@/components/ui/misc";
import { CatalogToggle } from "@/features/courses/CatalogToggle";
import { attribute, isEstimate, round1 } from "@/features/planner/metrics";
import { cn } from "@/lib/utils";

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

export function CourseRow({ c }: { c: CourseSummary }) {
  const hours = attribute(c, "workload_hours");
  const diff = attribute(c, "difficulty");
  return (
    <Card as="li" interactive className="relative flex flex-col gap-3">
      <Link
        to={`/courses/${encodeURIComponent(c.code)}`}
        className="flex flex-col gap-1 rounded-xs text-ink after:absolute after:inset-0 after:rounded-xl hover:[&>span:last-child]:underline"
      >
        <CourseCode>{c.code}</CourseCode> <span className="sr-only">·</span>{" "}
        <span className="text-title-md underline-offset-4">{c.title}</span>
      </Link>
      <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 text-caption text-muted">
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
    </Card>
  );
}

export default function CoursesPage() {
  const [sp, setSp] = useSearchParams();
  const params = paramsFrom(sp);
  const [draft, setDraft] = useState(() => Object.fromEntries(sp.entries()));
  // Nothing is listed until the student searches (FEEDBACK 2026-11-16: a simple, centered search).
  const searched = [...sp.entries()].some(([k, v]) => k !== "offset" && v);
  const filtered = [...sp.entries()].some(
    ([k, v]) => k !== "offset" && k !== "q" && v,
  );
  const q = useCourseSearch(params, searched);
  const id = useId();
  const field = (k: string) => `${id}-${k}`;
  const box = controlClass;

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

  return (
    <PageContainer>
      <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-5 pt-4 text-center sm:pt-8">
        <CatalogToggle current="courses" />
        <h1 className="font-display text-display-md text-ink">Course search</h1>
        <form
          onSubmit={submit}
          className="w-full text-left"
          aria-label="Course filters"
        >
          <div className="flex w-full gap-2">
            <label htmlFor={field("q")} className="sr-only">
              Code or title
            </label>
            <input
              id={field("q")}
              type="search"
              className={cn(box, "min-w-0 flex-1")}
              placeholder="Code or title"
              value={draft.q ?? ""}
              onChange={set("q")}
            />
            <Button type="submit">Search</Button>
          </div>
          <details className="group mt-3" open={filtered}>
            {/* D11 CS-2: a chevron shows it opens. */}
            <summary className="mx-auto flex min-h-11 w-fit cursor-pointer list-none items-center gap-1.5 rounded-md px-2 text-body-sm text-body hover:text-ink [&::-webkit-details-marker]:hidden">
              <ChevronIcon className="size-4 text-muted transition-transform duration-150 group-open:rotate-90 motion-reduce:transition-none" />
              More filters
            </summary>
            <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-4 rounded-lg border border-hairline bg-surface-card p-4 sm:gap-4 lg:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor={field("subject")}
                  className="text-caption font-medium text-ink"
                >
                  Department
                </label>
                <input
                  id={field("subject")}
                  className={box}
                  placeholder="e.g. CMSC"
                  value={draft.subject ?? ""}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      subject: e.target.value.toUpperCase(),
                    }))
                  }
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor={field("level")}
                  className="text-caption font-medium text-ink"
                >
                  Level
                </label>
                <select
                  id={field("level")}
                  className={box}
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
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor={field("quarter")}
                  className="text-caption font-medium text-ink"
                >
                  Quarter offered
                </label>
                <select
                  id={field("quarter")}
                  className={box}
                  value={draft.quarter ?? ""}
                  onChange={set("quarter")}
                >
                  {QUARTER_OPTIONS.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor={field("core")}
                  className="text-caption font-medium text-ink"
                >
                  Core area
                </label>
                <input
                  id={field("core")}
                  className={box}
                  placeholder="e.g. arts"
                  value={draft.core_tag ?? ""}
                  onChange={set("core_tag")}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor={field("hours")}
                  className="text-caption font-medium text-ink"
                >
                  Max hours/week
                </label>
                <input
                  id={field("hours")}
                  type="number"
                  min={0}
                  className={box}
                  value={draft.max_workload_hours ?? ""}
                  onChange={set("max_workload_hours")}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor={field("diff")}
                  className="text-caption font-medium text-ink"
                >
                  Max difficulty
                </label>
                <select
                  id={field("diff")}
                  className={box}
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
              </div>
              <div className="col-span-2 flex items-end gap-3 lg:col-span-3">
                <Button type="submit" variant="outline">
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
      </div>

      {searched && (
        <section aria-label="Results" className="mt-10">
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
              <p className="text-caption text-muted" role="status">
                {q.data?.total ?? 0} course{q.data?.total === 1 ? "" : "s"}
              </p>
              {(q.data?.total ?? 0) === 0 ? (
                // D11 CS-4: a way out instead of an empty list and dead paging.
                <EmptyState
                  title="No courses match"
                  className="mt-4"
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
              <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {q.data?.items.map((c) => (
                  <CourseRow key={c.code} c={c} />
                ))}
              </ul>
              )}
              {/* Paging only when there is more than one page. */}
              {(q.data?.total ?? 0) > PAGE && (
              <div className="mt-8 flex gap-3">
                <Button
                  variant="outline"
                  disabled={(params.offset ?? 0) === 0}
                  onClick={() => page(Math.max(0, (params.offset ?? 0) - PAGE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  disabled={(params.offset ?? 0) + PAGE >= (q.data?.total ?? 0)}
                  onClick={() => page((params.offset ?? 0) + PAGE)}
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
