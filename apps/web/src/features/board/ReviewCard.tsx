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
      data-spotlight="" className="qg-tile qg-tile-link group flex flex-col gap-3 px-5 py-5 sm:px-8 sm:py-7"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex min-h-6 items-center rounded-pill bg-white/[0.06] px-2.5 font-mono text-[10.5px] font-medium uppercase tracking-[0.14em] text-ink shadow-[inset_0_0_0_1px_rgb(255_255_255/0.12)]">Review</span>
        <span className="inline-flex min-h-6 items-center gap-1 rounded-pill bg-primary-wash px-2.5 text-[12px] font-semibold tabular-nums text-primary shadow-[inset_0_0_0_1px_rgb(255_120_140/0.3)]">
          <span aria-hidden="true">★</span>
          <span>
            {review.overall}
            <span className="font-normal">/5</span>
            <span className="sr-only"> overall</span>
          </span>
        </span>
        <span className="text-caption text-muted">{review.would_recommend ? "Would recommend" : "Would not recommend"}</span>
      </div>
      <h3 id={titleId} className="font-display text-[26px] leading-[1.15] tracking-[-0.2px] text-ink sm:text-[30px]">
        <Link to={href} className="rounded-xs transition-colors duration-300 hover:text-primary-hover focus-visible:text-primary-hover">
          {title}
        </Link>
      </h3>
      {review.excerpt && <p className="line-clamp-3 text-body-sm text-body">{review.excerpt}</p>}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2 pt-1">
        <CourseChip course={review.course} />
        <Link
          to={pagePath(review.course.code, review.instructor.slug)}
          className="relative inline-flex min-h-8 items-center rounded-pill bg-white/[0.04] px-3 text-caption text-ink shadow-[inset_0_0_0_1px_rgb(255_255_255/0.12)] transition-shadow duration-300 before:absolute before:inset-x-0 before:-inset-y-1.5 hover:shadow-[inset_0_0_0_1px_rgb(255_120_140/0.5)]"
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
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-hairline pt-2">
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
