import { useId, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowIcon } from "@/components/ui/icons";
import { courseHref, type CourseItem } from "../api";
import { CourseArt } from "../art/CourseArt";
import { Meta, ReasonChip } from "./parts";

/**
 * A course spotlight in the Catalog's browse row (issue #19, moved from the Feed): generated art
 * with the code set into it, the title, an excerpt of the catalog description, why it is here,
 * review stats, the student rating (`rating`, logged in only) and the Forum questions about it.
 * The Feed's flying keywords, book shelf, AI note and Save / Show less went with the Feed.
 */
export function CourseSpotlightCard({ item, rating }: { item: CourseItem; rating?: ReactNode }) {
  const titleId = useId();
  const href = courseHref(item.code);
  const stats = item.stats;

  return (
    <article
      aria-labelledby={titleId}
      className="feed-spotlight group relative flex h-full flex-col overflow-hidden rounded-xl border border-hairline bg-surface-card transition-shadow hover:shadow-hover focus-within:shadow-hover"
    >
      <div className="relative aspect-[16/10] overflow-hidden border-b border-hairline">
        <CourseArt
          code={item.code}
          motif={item.illustration.motif}
          seed={item.illustration.seed}
          paletteIndex={item.illustration.palette}
          className="feed-art block h-full w-full"
        />
        <span className="absolute left-3 top-3 max-w-[60%] truncate rounded-pill bg-surface-card/90 px-3 py-1 text-caption-uppercase uppercase text-ink">
          {item.category.label}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <ReasonChip>{item.reason}</ReasonChip>
        <h3 id={titleId} className="font-display text-[22px] font-bold leading-[1.15] tracking-[-0.2px] text-ink">
          <Link to={href} className="rounded-xs hover:text-primary focus-visible:text-primary">
            {item.title}
          </Link>
        </h3>
        <Meta>
          <span className="text-caption-uppercase uppercase text-muted">{item.code}</span>
          <span aria-hidden="true">·</span>
          <span>{item.units} units</span>
          {item.core_tags.length > 0 && (
            <>
              <span aria-hidden="true">·</span>
              <span>In the Core</span>
            </>
          )}
        </Meta>
        {item.excerpt && <p className="line-clamp-4 text-body-sm text-body">{item.excerpt}</p>}
        {rating}
        {stats && stats.n > 0 && (stats.workload_hours != null || stats.difficulty != null) && (
          <dl className="flex flex-wrap gap-x-5 gap-y-1 text-caption text-muted">
            {stats.workload_hours != null && (
              <div className="flex gap-1">
                <dt>Workload</dt>
                <dd className="font-medium text-ink">{stats.workload_hours} h/week</dd>
              </div>
            )}
            {stats.difficulty != null && (
              <div className="flex gap-1">
                <dt>Difficulty</dt>
                <dd className="font-medium text-ink">{stats.difficulty} / 5</dd>
              </div>
            )}
            <div className="flex gap-1">
              <dt className="sr-only">Based on</dt>
              <dd>
                {stats.n} {stats.n === 1 ? "review" : "reviews"}
              </dd>
            </div>
          </dl>
        )}
        {item.commons_count > 0 && (
          // type=discussion: since issue #20 /forum also lists reviews; this link counts questions only.
          <Link to={`/forum?course=${encodeURIComponent(item.code)}&type=discussion`} className="text-caption text-primary underline underline-offset-2">
            {item.commons_count} {item.commons_count === 1 ? "question" : "questions"} about it in the Forum
          </Link>
        )}
        <Link
          to={href}
          className="-mx-2 mt-auto inline-flex min-h-11 items-center gap-1.5 self-start rounded-pill px-2 text-button text-primary hover:text-primary-hover"
          aria-label={`Open course ${item.code}`}
        >
          Open course <ArrowIcon size={14} />
        </Link>
      </div>
    </article>
  );
}
