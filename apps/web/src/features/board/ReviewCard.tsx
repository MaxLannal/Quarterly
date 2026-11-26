import { Link } from "react-router-dom";
import { CourseChip, Day, Handle } from "@/features/commons/parts";
import { pagePath, plural, threadPath } from "@/features/forum/format";
import { VoteControl } from "@/features/forum/parts";
import { termLabel } from "@/features/planner/terms";
import type { ReviewItem } from "./api";

/** A course review in the `/forum` list (issue #20), in the manner of the discussion cards. */
export function ReviewCard({ review }: { review: ReviewItem }) {
  const titleId = `review-${review.id}-title`;
  const href = threadPath(review.course.code, review.instructor.slug, review.id);
  const title = review.title || `${review.course.code} with ${review.instructor.display_name}`;
  return (
    <article
      aria-labelledby={titleId}
      className="group relative flex flex-col gap-2 rounded-xl border border-hairline bg-surface-card px-4 py-4 transition-shadow hover:shadow-hover focus-within:shadow-hover sm:px-6 sm:py-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex min-h-6 items-center rounded-pill bg-surface-strong px-2.5 text-[12px] font-semibold text-ink">Review</span>
        <span className="inline-flex min-h-6 items-center gap-1 rounded-pill bg-primary-wash px-2.5 text-[12px] font-semibold tabular-nums text-primary">
          <span aria-hidden="true">★</span>
          <span>
            {review.overall}
            <span className="font-normal">/5</span>
            <span className="sr-only"> overall</span>
          </span>
        </span>
        <span className="text-caption text-muted">{review.would_recommend ? "Would recommend" : "Would not recommend"}</span>
      </div>
      <h3 id={titleId} className="font-display text-[21px] font-bold leading-snug tracking-[-0.02em] text-ink sm:text-[23px]">
        <Link to={href} className="rounded-xs decoration-primary/40 underline-offset-4 hover:underline focus-visible:underline">
          {title}
        </Link>
      </h3>
      {review.excerpt && <p className="line-clamp-3 text-body-sm text-body">{review.excerpt}</p>}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2 pt-1">
        <CourseChip course={review.course} />
        <Link
          to={pagePath(review.course.code, review.instructor.slug)}
          className="relative inline-flex min-h-8 items-center rounded-pill border border-hairline-strong px-3 text-caption text-ink before:absolute before:inset-x-0 before:-inset-y-1.5 hover:border-primary/50"
        >
          {review.instructor.display_name}
        </Link>
      </div>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">
        <span>Difficulty {review.difficulty}/5</span>
        <span aria-hidden="true">·</span>
        <span>{review.workload_hours} h a week</span>
        {review.term_taken && (
          <>
            <span aria-hidden="true">·</span>
            <span>took it in {termLabel(review.term_taken)}</span>
          </>
        )}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">
          <span>
            reviewed by <Handle handle={review.handle} mine={review.is_mine} />
          </span>
          <span aria-hidden="true">·</span>
          <Day day={review.created_day} edited={review.edited_day} />
          <span aria-hidden="true">·</span>
          <Link to={href} className="inline-flex min-h-11 items-center rounded-xs font-medium text-ink hover:text-primary">
            {plural(review.n_comments, "comment")}
          </Link>
        </p>
        <VoteControl targetType="post" targetId={review.id} score={review.score} myVote={review.my_vote} label={`the review “${title}”`} />
      </div>
    </article>
  );
}
