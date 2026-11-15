import { Link, useParams } from "react-router-dom";
import { useAuthLinks } from "@/features/auth/next";
import { ApiError } from "@/api/client";
import { EmptyState, inlineLinkClass, LoadingState, PageContainer, PageHeader, Section, standaloneLinkClass } from "@/components/layout/page";
import { Card } from "@/components/ui/card";
import { CourseCode, Dots, Notice } from "@/components/ui/misc";
import { useSession } from "@/features/auth/session";
import { useInstructor } from "@/features/forum/api";
import { pagePath, plural } from "@/features/forum/format";

/** Instructor page (SPEC "Instructor page"): name, department and courses taught. Per-course
 * ratings only for logged-in readers; nothing personal beyond what the University publishes. */
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
  return (
    <PageContainer as="article" width="reading">
      <PageHeader eyebrow="Instructor" title={i.display_name} meta={i.department ? <span>{i.department}</span> : undefined} />
      <Section id="courses" title="Courses taught" description={plural(courses.length, "course")}>
        {!loggedIn && (
          <Notice tone="info" className="mb-4">
            <p>
              <Link to={authLinks.login}>Log in</Link> to see ratings and read reviews.
            </p>
          </Notice>
        )}
        {courses.length === 0 ? (
          <EmptyState title="No courses recorded yet" />
        ) : (
          <ul className="flex flex-col gap-3">
            {courses.map((c) => {
              const r = c.ratings;
              return (
                <li key={c.code}>
                  <Card variant="compact" className="flex flex-col gap-2">
                    <CourseCode>{c.code}</CourseCode>
                    <p className="text-title-sm text-ink">{c.title}</p>
                    <p className="text-caption text-muted">
                      {plural(c.n_terms ?? 0, "term")} recorded
                      {r ? ` · ${plural(r.n_reviews ?? 0, "review")}` : ""}
                    </p>
                    {r && (r.n_reviews ?? 0) > 0 && (
                      <dl className="flex flex-wrap gap-x-6 gap-y-1 text-caption text-muted">
                        <div className="flex items-center gap-2">
                          <dt>Overall</dt>
                          <dd className="flex items-center gap-1.5 text-ink">
                            <Dots value={r.overall ?? 0} label="Overall" /> {(r.overall ?? 0).toFixed(1)}
                          </dd>
                        </div>
                        <div className="flex items-center gap-2">
                          <dt>Difficulty</dt>
                          <dd className="text-ink">{(r.difficulty ?? 0).toFixed(1)}</dd>
                        </div>
                        <div className="flex items-center gap-2">
                          <dt>Workload</dt>
                          <dd className="text-ink">{(r.workload_hours ?? 0).toFixed(1)} h/wk</dd>
                        </div>
                      </dl>
                    )}
                    <div className="flex flex-wrap gap-x-4">
                      {loggedIn && (
                        <Link to={pagePath(c.code, i.slug)} className={`${inlineLinkClass} inline-flex min-h-11 items-center`}>
                          Reviews and discussion
                        </Link>
                      )}
                      <Link to={`/courses/${encodeURIComponent(c.code)}`} className={`${inlineLinkClass} inline-flex min-h-11 items-center`}>
                        Course page
                      </Link>
                    </div>
                  </Card>
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </PageContainer>
  );
}
