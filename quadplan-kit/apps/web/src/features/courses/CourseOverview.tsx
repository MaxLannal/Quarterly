import { Link } from "react-router-dom";
import type { CourseDetail } from "@/api/types";
import { inlineLinkClass } from "@/components/layout/page";
import { useAuthLinks } from "@/features/auth/next";
import { useSession } from "@/features/auth/session";
import { useCourseForum } from "@/features/forum/api";
import { pagePath, plural } from "@/features/forum/format";
import { termLabel } from "@/features/planner/terms";
import { cn } from "@/lib/utils";

const fmt = (n: number | null | undefined) => (n == null ? "–" : n.toFixed(1));

/**
 * Instructors and student ratings at a glance, under the course title (FEEDBACK 2026-11-16:
 * "a compacted overview below the title and above prerequisite"). Ratings need a login.
 */
export function CourseOverview({ course }: { course: CourseDetail }) {
  const session = useSession();
  const authLinks = useAuthLinks();
  const loggedIn = session.status === "authenticated";
  const forum = useCourseForum(course.code, loggedIn);
  const pages = new Map((forum.data?.pages ?? []).map((p) => [p.instructor.slug, p]));
  const pooled = forum.data?.ratings;
  const n = pooled?.n_reviews ?? 0;

  return (
    <section aria-labelledby="overview-heading" className="mb-8 rounded-lg border border-hairline bg-surface-card px-4 py-3">
      <h2 id="overview-heading" className="sr-only">
        Overview
      </h2>
      <dl className="grid gap-x-8 gap-y-3 text-body-sm md:grid-cols-[minmax(12rem,auto)_1fr]">
        <div id="student-ratings">
          <dt className="text-caption-uppercase uppercase text-muted">Student ratings</dt>
          <dd className="mt-1 tabular-nums text-ink">
            {!loggedIn ? (
              <>
                <Link to={authLinks.login} className={inlineLinkClass}>
                  Log in
                </Link>{" "}
                to see ratings.
              </>
            ) : forum.isLoading ? (
              <span className="text-muted">Loading…</span>
            ) : n === 0 ? (
              <span className="text-muted">No reviews yet.</span>
            ) : (
              <>
                <span className="text-body-strong">{fmt(pooled?.overall)} / 5</span> overall · difficulty {fmt(pooled?.difficulty)} / 5 ·{" "}
                {fmt(pooled?.workload_hours)} h/wk · <span className="text-muted">{plural(n, "review")}</span>
              </>
            )}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-caption-uppercase uppercase text-muted">Instructors</dt>
          <dd className="mt-1">
            {course.instructors.length === 0 ? (
              <span className="text-muted">No instructors recorded yet.</span>
            ) : (
              <ul className="flex flex-wrap gap-x-5" aria-label="Instructors">
                {course.instructors.map((i) => {
                  const page = pages.get(i.instructor.slug);
                  const reviews = page?.ratings?.n_reviews ?? 0;
                  const when = i.first_term && i.last_term ? `${termLabel(i.first_term)}–${termLabel(i.last_term)}` : plural(i.n_terms, "term");
                  return (
                    <li key={i.instructor.slug} className="flex min-h-11 items-baseline gap-1.5 py-2">
                      <Link to={pagePath(course.code, i.instructor.slug)} className={cn(inlineLinkClass, "text-body-strong")}>
                        {i.instructor.display_name}
                      </Link>
                      <span className="text-caption text-muted tabular-nums">
                        {loggedIn && reviews > 0 ? `${fmt(page?.ratings?.overall)} / 5 (${reviews})` : when}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}
