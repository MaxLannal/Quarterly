import { Link } from "react-router-dom";
import { inlineLinkClass, Section } from "@/components/layout/page";
import { Notice, Spinner } from "@/components/ui/misc";
import { useSession } from "@/features/auth/session";
import { useCourseForum } from "./api";
import { pagePath, plural } from "./format";
import { RatingStats } from "./parts";

/**
 * Course-level view (SPEC "Forum > Structure"): every instructor's page of this course, ratings
 * pooled. Ratings need a login; the instructor names themselves are public on the course page.
 */
export function CourseForumSummary({ code }: { code: string }) {
  const session = useSession();
  const loggedIn = session.status === "authenticated";
  const q = useCourseForum(code, loggedIn);

  return (
    <Section id="student-ratings" title="Student ratings" description="Pooled across every instructor who teaches it.">
      {session.status === "loading" ? (
        <Spinner />
      ) : !loggedIn ? (
        <Notice tone="info">
          <p>
            <Link to="/login">Log in</Link> to see ratings and read reviews from students.
          </p>
        </Notice>
      ) : q.isLoading ? (
        <Spinner label="Loading ratings" />
      ) : !q.data || (q.data.pages ?? []).length === 0 ? (
        <p className="text-body-sm text-muted">No forum pages for this course yet.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <RatingStats ratings={q.data.ratings ?? { n_reviews: 0 }} />
          <p className="text-caption text-muted">From {plural(q.data.ratings?.n_reviews ?? 0, "review")}</p>
          <ul className="divide-y divide-hairline border-y border-hairline">
            {(q.data.pages ?? []).map((p) => (
              <li key={p.page_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <Link to={pagePath(q.data.course_code, p.instructor.slug)} className={`${inlineLinkClass} inline-flex min-h-11 items-center text-body-strong`}>
                  {p.instructor.display_name}
                </Link>
                <span className="text-caption text-muted tabular-nums">
                  {(p.ratings?.n_reviews ?? 0) > 0
                    ? `${(p.ratings?.overall ?? 0).toFixed(1)} / 5 overall · ${plural(p.ratings?.n_reviews ?? 0, "review")}`
                    : "No reviews yet"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}
