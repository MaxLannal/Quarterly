import { Link, useParams } from "react-router-dom";
import { useAuthLinks } from "@/features/auth/next";
import { ApiError } from "@/api/client";
import { EmptyState, LoadingState, PageContainer, PageHeader, standaloneLinkClass, tallTargetClass } from "@/components/layout/page";
import { ArrowIcon } from "@/components/ui/icons";
import { CourseCode } from "@/components/ui/misc";
import { useSession } from "@/features/auth/session";
import { FactChip, FactChips, Kicker, RatingRing } from "@/features/courses/Glass";
import { useInstructor } from "@/features/forum/api";
import { pagePath, plural } from "@/features/forum/format";
import { cn } from "@/lib/utils";

/** Instructor page (SPEC "Instructor page"): name, department and courses taught. Per-course
 * ratings only for logged-in readers; nothing personal beyond what the University publishes.
 * Dark glass: the course page's cover language (kicker, display serif, fact chips), then the
 * courses as glass tiles, each with its rating ring when there are reviews. */
export default function InstructorPage() {
  const { slug = "" } = useParams();
  const session = useSession();
  const authLinks = useAuthLinks();
  const loggedIn = session.status === "authenticated";
  const q = useInstructor(slug, loggedIn);

  if (q.isLoading || session.status === "loading") {
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title="Instructor" size="md" />
        <LoadingState label="Loading instructor" />
      </PageContainer>
    );
  }
  if (q.error || !q.data) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title={missing ? "Instructor not found" : "Instructor"} size="md" />
        <Link to="/instructors" className={standaloneLinkClass}>
          All instructors
        </Link>
      </PageContainer>
    );
  }

  const i = q.data;
  const courses = i.courses ?? [];
  const reviews = courses.reduce((n, c) => n + (c.ratings?.n_reviews ?? 0), 0);
  return (
    <PageContainer as="article" className="max-w-[1240px]">
      <header className="qg-hero pb-12 pt-4 sm:pt-12">
        <Kicker className="mb-5">
          <Link to="/instructors" className={cn("hover:text-ink", tallTargetClass)}>
            Forum
          </Link>{" "}
          <span className="text-muted-soft">//</span> Instructor
        </Kicker>
        <h1 className="font-display text-display-lg text-ink [text-shadow:0_0_60px_rgb(255_92_112/0.22)] sm:text-display-mega">{i.display_name}</h1>
        <FactChips label="About this instructor" className="mt-8">
          <FactChip label="Role">Instructor</FactChip>
          {i.department && <FactChip label="Department">{i.department}</FactChip>}
          <FactChip label="Courses taught">{courses.length}</FactChip>
          {loggedIn && <FactChip label="Reviews" tone={reviews > 0 ? "ember" : undefined}>{reviews}</FactChip>}
        </FactChips>
      </header>

      <section id="courses" aria-labelledby="courses-heading" className="scroll-mt-24">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-hairline pb-4">
          <div className="flex flex-col gap-2">
            <Kicker>01 <span className="text-muted-soft">//</span> Teaching</Kicker>
            <h2 id="courses-heading" className="font-display text-display-sm text-ink sm:text-display-md">
              Courses taught
            </h2>
          </div>
          <p className="font-mono text-[11.5px] uppercase tracking-[0.16em] text-muted">{plural(courses.length, "course")}</p>
        </div>
        {!loggedIn && (
          <p className="qg-tile mb-6 px-6 py-5 text-body-sm text-body">
            <Link to={authLinks.login} className="text-primary underline underline-offset-2">
              Log in
            </Link>{" "}
            to see ratings and read reviews.
          </p>
        )}
        {courses.length === 0 ? (
          <EmptyState title="No courses recorded yet" />
        ) : (
          <ul className="grid gap-4 md:grid-cols-2">
            {courses.map((c) => {
              const r = c.ratings;
              const rated = !!r && (r.n_reviews ?? 0) > 0;
              return (
                <li key={c.code} className="qg-tile flex flex-col gap-4 p-6 sm:p-7">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex min-w-0 flex-col gap-1.5">
                      <CourseCode>{c.code}</CourseCode>
                      <p className="font-display text-[28px] leading-[1.15] text-ink">{c.title}</p>
                      <p className="text-caption text-muted">
                        {plural(c.n_terms ?? 0, "term")} recorded
                        {r ? ` · ${plural(r.n_reviews ?? 0, "review")}` : ""}
                      </p>
                    </div>
                    {rated && r && (
                      <RatingRing value={r.overall} size={68} stroke={4}>
                        <span aria-hidden="true" className="qg-numeral text-[24px]">
                          {(r.overall ?? 0).toFixed(1)}
                        </span>
                      </RatingRing>
                    )}
                  </div>
                  {rated && r && (
                    <dl className="flex flex-wrap gap-2 text-caption">
                      <div className="qg-chip min-h-0 gap-1 rounded-[14px] px-3.5 py-2">
                        <dt className="qg-chip-label">Overall</dt>
                        <dd className="text-caption font-medium tabular-nums text-ink">{(r.overall ?? 0).toFixed(1)}</dd>
                      </div>
                      <div className="qg-chip min-h-0 gap-1 rounded-[14px] px-3.5 py-2">
                        <dt className="qg-chip-label">Difficulty</dt>
                        <dd className="text-caption font-medium tabular-nums text-ink">{(r.difficulty ?? 0).toFixed(1)}</dd>
                      </div>
                      <div className="qg-chip min-h-0 gap-1 rounded-[14px] px-3.5 py-2">
                        <dt className="qg-chip-label">Workload</dt>
                        <dd className="text-caption font-medium tabular-nums text-ink">{(r.workload_hours ?? 0).toFixed(1)} h/wk</dd>
                      </div>
                    </dl>
                  )}
                  <div className="mt-auto flex flex-wrap gap-x-5 border-t border-hairline pt-2">
                    {loggedIn && (
                      <Link to={pagePath(c.code, i.slug)} className="group inline-flex min-h-11 items-center gap-2 text-button text-ink hover:text-primary-hover">
                        Reviews and discussion
                        <ArrowIcon size={14} className="transition-transform duration-300 group-hover:translate-x-0.5" />
                      </Link>
                    )}
                    <Link to={`/courses/${encodeURIComponent(c.code)}`} className="inline-flex min-h-11 items-center text-button text-body hover:text-ink">
                      Course page
                    </Link>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </PageContainer>
  );
}
