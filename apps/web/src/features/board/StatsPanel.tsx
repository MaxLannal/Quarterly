/**
 * The left third of `/forum` (issue #20): rating statistics and rankings for logged-in students
 * (the rule the course pages already follow). Scores are Bayesian averages of the overall rating
 * (docs/SPEC.md, k = 5); only subjects with at least 3 reviews are ranked, each with its count.
 */
import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorText } from "@/components/ui/misc";
import { LoginCard } from "@/features/commons/parts";
import { plural } from "@/features/forum/format";
import { cn } from "@/lib/utils";
import { PERIODS, score, useForumStats, type ForumStats, type Period, type RankedEntry } from "./api";

function Ranking({
  title,
  entries,
  empty,
  href,
}: {
  title: string;
  entries: RankedEntry[];
  empty: string;
  href?: (entry: RankedEntry) => string;
}) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-1">
      <h3 id={id} className="text-caption-uppercase uppercase text-muted">
        {title}
      </h3>
      {entries.length === 0 ? (
        <p className="py-2 text-caption text-muted">{empty}</p>
      ) : (
        <ol className="flex flex-col">
          {entries.map((e) => {
            const body = (
              <>
                <span aria-hidden="true" className="w-5 shrink-0 text-right text-caption tabular-nums text-muted">
                  {e.rank}
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-semibold text-ink group-hover:text-primary">
                    <span className="sr-only">{`Rank ${e.rank}: `}</span>
                    {e.label}
                  </span>
                  {e.detail && <span className="truncate text-caption text-muted">{e.detail}</span>}
                </span>
                <span className="flex shrink-0 flex-col items-end">
                  <span className="font-semibold tabular-nums text-ink">
                    <span className="sr-only">, score </span>
                    {score(e.score)}
                  </span>
                  <span className="text-caption tabular-nums text-muted">
                    <span className="sr-only">, </span>
                    {plural(e.n_reviews, "review")}
                  </span>
                </span>
              </>
            );
            const row = "flex min-h-11 items-center gap-3 py-1.5";
            return (
              <li key={e.id} className="border-b border-hairline last:border-b-0">
                {href ? (
                  <Link to={href(e)} className={cn(row, "group rounded-sm")}>
                    {body}
                  </Link>
                ) : (
                  <div className={row}>{body}</div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function Summary({ stats }: { stats: ForumStats }) {
  if (stats.n_reviews === 0) return <p className="text-body-sm text-muted">No reviews in this period yet.</p>;
  const facts = [
    `${plural(stats.n_reviews, "review")} of ${plural(stats.n_courses, "course")}`,
    stats.prior_mean != null ? `average ${score(stats.prior_mean)}/5` : null,
    stats.recommend_rate != null ? `${Math.round(stats.recommend_rate * 100)}% would recommend` : null,
    stats.workload_hours != null ? `${stats.workload_hours} h a week outside class` : null,
  ].filter(Boolean);
  return (
    <ul aria-label="This period in numbers" className="flex flex-wrap gap-x-3 gap-y-1 text-body-sm text-body">
      {facts.map((f) => (
        <li key={f}>{f}</li>
      ))}
    </ul>
  );
}

function Majors({ stats, courseHref }: { stats: ForumStats; courseHref: (code: string) => string }) {
  const selectId = useId();
  const withItems = stats.majors.find((m) => m.items.length > 0);
  const [chosen, setChosen] = useState<string>("");
  const current = stats.majors.find((m) => m.program_id === chosen) ?? withItems ?? stats.majors[0];
  if (!current) return null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <label htmlFor={selectId} className="shrink-0 text-caption-uppercase uppercase text-muted">
          Top in the major
        </label>
        <select
          id={selectId}
          value={current.program_id}
          onChange={(e) => setChosen(e.target.value)}
          className="min-h-11 min-w-0 flex-1 rounded-md border border-hairline-strong bg-surface-card px-2 text-caption text-ink"
        >
          {stats.majors.map((m) => (
            <option key={m.program_id} value={m.program_id}>
              {m.name}
            </option>
          ))}
        </select>
      </div>
      <Ranking title={current.name} entries={current.items} empty="No course in this major has 3 reviews yet." href={(e) => courseHref(e.id)} />
    </div>
  );
}

/** Statistics and rankings. `loggedIn: false` shows a login card instead (no request is made). */
export function StatsPanel({
  loggedIn,
  courseHref,
  instructorHref,
}: {
  loggedIn: boolean;
  courseHref: (code: string) => string;
  instructorHref: (slug: string) => string;
}) {
  const [period, setPeriod] = useState<Period>("quarter");
  const stats = useForumStats(period, loggedIn);
  return (
    <section aria-labelledby="forum-stats-title" className="relative flex flex-col gap-5 overflow-hidden rounded-xl border border-hairline bg-surface-card p-5 sm:p-6">
      <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-primary" />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="forum-stats-title" className="font-display text-display-sm text-ink">
          Ratings
        </h2>
        {loggedIn && (
          <div role="group" aria-label="Period" className="inline-flex rounded-pill bg-surface-strong p-0.5">
            {PERIODS.map((p) => (
              <button
                key={p.key}
                type="button"
                aria-pressed={period === p.key}
                onClick={() => setPeriod(p.key)}
                className={cn(
                  "inline-flex min-h-11 items-center rounded-pill px-3 text-caption font-medium transition-colors",
                  period === p.key ? "bg-surface-card text-primary shadow-hover" : "text-body hover:text-ink",
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
      </div>
      {!loggedIn ? (
        <LoginCard className="sm:flex-col sm:items-start">Log in to see ratings, rankings and reviews. Your name never shows.</LoginCard>
      ) : stats.isLoading ? (
        <div aria-hidden="true" className="flex flex-col gap-3">
          <div className="skeleton h-4 w-3/4" />
          <div className="skeleton h-24 w-full" />
          <div className="skeleton h-24 w-full" />
        </div>
      ) : stats.isError ? (
        <ErrorText>{stats.error.message}</ErrorText>
      ) : stats.data ? (
        <>
          <Summary stats={stats.data} />
          <Ranking title="Top courses" entries={stats.data.top_courses} empty="No course has 3 reviews in this period yet." href={(e) => courseHref(e.id)} />
          {stats.data.majors.length > 0 && <Majors stats={stats.data} courseHref={courseHref} />}
          <Ranking title="Humanities sequences" entries={stats.data.humanities} empty="No Humanities sequence has 3 reviews in this period yet." />
          <Ranking title="Instructors" entries={stats.data.instructors} empty="No instructor has 3 reviews in this period yet." href={(e) => instructorHref(e.id)} />
          <p className="text-caption text-muted">
            Scores are Bayesian averages of the overall rating: each starts from this period&apos;s average
            {stats.data.prior_mean != null ? ` (${score(stats.data.prior_mean)})` : ""} as if it had {stats.data.prior_weight} reviews, and moves toward its own
            ratings as reviews come in. Ranked only with {stats.data.min_reviews} reviews or more.
          </p>
        </>
      ) : null}
    </section>
  );
}
