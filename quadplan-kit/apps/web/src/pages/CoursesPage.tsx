import { useId, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { isNotAvailable } from "@/api/client";
import { useCourseSearch, type CourseSearchParams } from "@/api/hooks";
import type { CourseSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge, Dots, NotAvailable, Spinner } from "@/components/ui/misc";
import { attribute, isEstimate, round1 } from "@/features/planner/metrics";

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
    <li className="rounded-md border border-border p-3">
      <Link to={`/courses/${encodeURIComponent(c.code)}`} className="font-semibold text-primary hover:underline">
        {c.code} · {c.title}
      </Link>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
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
    </li>
  );
}

export default function CoursesPage() {
  const [sp, setSp] = useSearchParams();
  const params = paramsFrom(sp);
  const [draft, setDraft] = useState(() => Object.fromEntries(sp.entries()));
  const q = useCourseSearch(params);
  const id = useId();
  const field = (k: string) => `${id}-${k}`;
  const box = "min-h-11 w-full rounded-md border border-border bg-background px-2 text-sm";

  function submit(e: FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams();
    for (const [k, v] of Object.entries(draft)) if (v && k !== "offset") next.set(k, v);
    setSp(next);
  }
  function page(offset: number) {
    const next = new URLSearchParams(sp);
    next.set("offset", String(offset));
    setSp(next);
  }
  const set = (k: string) => (e: { target: { value: string } }) => setDraft((d) => ({ ...d, [k]: e.target.value }));
  // Keep the form in sync when the header search changes the URL.
  const urlQ = sp.get("q") ?? "";
  const [lastQ, setLastQ] = useState(urlQ);
  if (urlQ !== lastQ) {
    setLastQ(urlQ);
    setDraft((d) => ({ ...d, q: urlQ }));
  }

  return (
    <div className="mx-auto max-w-5xl p-4">
      <h1 className="text-2xl font-semibold">Course search</h1>
      <form onSubmit={submit} className="mt-3 grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Course filters">
        <div className="sm:col-span-2">
          <label htmlFor={field("q")} className="text-sm font-medium">
            Code or title
          </label>
          <input id={field("q")} className={box} value={draft.q ?? ""} onChange={set("q")} />
        </div>
        <div>
          <label htmlFor={field("subject")} className="text-sm font-medium">
            Department
          </label>
          <input id={field("subject")} className={box} placeholder="e.g. CMSC" value={draft.subject ?? ""} onChange={(e) => setDraft((d) => ({ ...d, subject: e.target.value.toUpperCase() }))} />
        </div>
        <div>
          <label htmlFor={field("level")} className="text-sm font-medium">
            Level
          </label>
          <select id={field("level")} className={box} value={draft.level ?? ""} onChange={set("level")}>
            <option value="">Any level</option>
            {[10000, 20000, 30000, 40000].map((l) => (
              <option key={l} value={l}>
                {l}s
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={field("quarter")} className="text-sm font-medium">
            Quarter offered
          </label>
          <select id={field("quarter")} className={box} value={draft.quarter ?? ""} onChange={set("quarter")}>
            {QUARTER_OPTIONS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={field("core")} className="text-sm font-medium">
            Core area
          </label>
          <input id={field("core")} className={box} placeholder="e.g. arts" value={draft.core_tag ?? ""} onChange={set("core_tag")} />
        </div>
        <div>
          <label htmlFor={field("hours")} className="text-sm font-medium">
            Max hours/week
          </label>
          <input id={field("hours")} type="number" min={0} className={box} value={draft.max_workload_hours ?? ""} onChange={set("max_workload_hours")} />
        </div>
        <div>
          <label htmlFor={field("diff")} className="text-sm font-medium">
            Max difficulty
          </label>
          <select id={field("diff")} className={box} value={draft.max_difficulty ?? ""} onChange={set("max_difficulty")}>
            <option value="">Any</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n} of 5
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-4">
          <Button type="submit">Search</Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setDraft({});
              setSp(new URLSearchParams());
            }}
          >
            Clear
          </Button>
        </div>
      </form>

      <section aria-label="Results" className="mt-4">
        {q.isLoading ? (
          <Spinner label="Searching" />
        ) : q.error ? (
          isNotAvailable(q.error) ? (
            <NotAvailable feature="Course search" />
          ) : (
            <p className="text-red-800">Could not load courses.</p>
          )
        ) : (
          <>
            <p className="text-sm text-muted-foreground" role="status">
              {q.data?.total ?? 0} course{q.data?.total === 1 ? "" : "s"}
            </p>
            <ul className="mt-2 space-y-2">
              {q.data?.items.map((c) => (
                <CourseRow key={c.code} c={c} />
              ))}
            </ul>
            <div className="mt-3 flex gap-2">
              <Button variant="outline" disabled={(params.offset ?? 0) === 0} onClick={() => page(Math.max(0, (params.offset ?? 0) - PAGE))}>
                Previous
              </Button>
              <Button variant="outline" disabled={(params.offset ?? 0) + PAGE >= (q.data?.total ?? 0)} onClick={() => page((params.offset ?? 0) + PAGE)}>
                Next
              </Button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
