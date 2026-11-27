import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { CourseDetail } from "@/api/types";
import { inlineLinkClass } from "@/components/layout/page";
import { useAuthLinks } from "@/features/auth/next";
import { useSession } from "@/features/auth/session";
import { useCourseForum } from "@/features/forum/api";
import { pagePath, plural } from "@/features/forum/format";
import { termLabel } from "@/features/planner/terms";
import { cn } from "@/lib/utils";
import { Meter, RatingRing } from "./Glass";

const fmt = (n: number | null | undefined) => (n == null ? "–" : n.toFixed(1));

const label = "font-mono text-[10.5px] font-medium uppercase tracking-[0.2em] text-muted";

/**
 * Instructors and student ratings at a glance (FEEDBACK 2026-11-16: "a compacted overview below
 * the title and above prerequisite"). Ratings need a login.
 *
 * Dark glass: the course page's side card. The pooled rating is a ring of red light with the
 * number in the display serif, difficulty and workload are thin meters, the instructors are glass
 * rows, and `action` (Add to plan) sits at the foot of the card.
 */
export function CourseOverview({ course, action }: { course: CourseDetail; action?: ReactNode }) {
  const session = useSession();
  const authLinks = useAuthLinks();
  const loggedIn = session.status === "authenticated";
  const forum = useCourseForum(course.code, loggedIn);
  const pages = new Map((forum.data?.pages ?? []).map((p) => [p.instructor.slug, p]));
  const pooled = forum.data?.ratings;
  const n = pooled?.n_reviews ?? 0;

  return (
    <section aria-labelledby="overview-heading" className="qg-tile qg-edge overflow-hidden p-6 sm:p-7">
      <span aria-hidden="true" className="pointer-events-none absolute -right-24 -top-24 size-64 rounded-pill bg-[radial-gradient(closest-side,rgb(220_30_60/0.28),transparent)]" />
      <h2 id="overview-heading" className="sr-only">
        Overview
      </h2>
      <dl className="relative flex flex-col gap-7 text-body-sm">
        <div id="student-ratings">
          <dt className={label}>Student ratings</dt>
          <dd className="mt-4 tabular-nums text-ink">
            {!loggedIn ? (
              <p className="text-body">
                <Link to={authLinks.login} className={inlineLinkClass}>
                  Log in
                </Link>{" "}
                to see ratings.
              </p>
            ) : forum.isLoading ? (
              <span className="text-muted">Loading…</span>
            ) : n === 0 ? (
              <span className="text-muted">No reviews yet.</span>
            ) : (
              <div className="flex flex-col gap-5">
                <div className="flex items-center gap-5">
                  <RatingRing value={pooled?.overall} size={96} stroke={6}>
                    <span aria-hidden="true" className="qg-numeral text-[38px]">
                      {fmt(pooled?.overall)}
                    </span>
                  </RatingRing>
                  <p className="flex flex-col gap-1">
                    <span className="text-body-strong text-ink">{fmt(pooled?.overall)} / 5 overall</span>
                    <span className="text-caption text-muted">{plural(n, "review")}</span>
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <p className="flex flex-col gap-2">
                    <span className="text-caption text-muted">Difficulty</span>
                    <span className="text-body-strong">{fmt(pooled?.difficulty)} / 5</span>
                    <Meter share={(pooled?.difficulty ?? 0) / 5} />
                  </p>
                  <p className="flex flex-col gap-2">
                    <span className="text-caption text-muted">Workload</span>
                    <span className="text-body-strong">{fmt(pooled?.workload_hours)} h/wk</span>
                    <Meter share={(pooled?.workload_hours ?? 0) / 20} />
                  </p>
                </div>
              </div>
            )}
          </dd>
        </div>
        <div className="min-w-0 border-t border-hairline pt-6">
          <dt className={label}>Instructors</dt>
          <dd className="mt-2">
            {course.instructors.length === 0 ? (
              <span className="text-muted">No instructors recorded yet.</span>
            ) : (
              <>
                {/* CP-3 (D11): the instructor links lead to the forum; say so. */}
                <p className="text-caption text-muted">Choose an instructor to read their reviews and discussion.</p>
                <ul className="mt-3 flex flex-col gap-2" aria-label="Instructors">
                  {course.instructors.map((i) => {
                    const page = pages.get(i.instructor.slug);
                    const reviews = page?.ratings?.n_reviews ?? 0;
                    const when = i.first_term && i.last_term ? `${termLabel(i.first_term)}–${termLabel(i.last_term)}` : plural(i.n_terms, "term");
                    return (
                      <li
                        key={i.instructor.slug}
                        className="group relative flex min-h-12 items-center justify-between gap-3 rounded-[16px] border border-hairline bg-white/[0.03] px-4 py-2 transition-[border-color,background-color] duration-300 hover:border-primary/40 hover:bg-white/[0.06]"
                      >
                        <Link
                          to={pagePath(course.code, i.instructor.slug)}
                          className={cn("inline-flex min-h-11 items-center rounded-xs text-body-strong text-ink after:absolute after:inset-0 after:rounded-[16px] group-hover:text-primary-hover")}
                        >
                          {i.instructor.display_name}
                        </Link>
                        <span className="shrink-0 font-mono text-[11.5px] tabular-nums tracking-[0.06em] text-muted">
                          {loggedIn && reviews > 0 ? `${fmt(page?.ratings?.overall)} / 5 (${reviews})` : when}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </dd>
        </div>
      </dl>
      {action && <div className="relative mt-7 border-t border-hairline pt-6 [&>div>button]:w-full">{action}</div>}
    </section>
  );
}
