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
 *
 * Dark glass: the art sits inset in the tile like a print under a pane, with a two-line glass
 * chip (category over code) floating on it; the title is the display serif.
 */
export function CourseSpotlightCard({ item, rating }: { item: CourseItem; rating?: ReactNode }) {
  const titleId = useId();
  const href = courseHref(item.code);
  const stats = item.stats;

  return (
    <article aria-labelledby={titleId} data-spotlight="" className="feed-spotlight qg-tile qg-tile-link group flex h-full flex-col p-3">
      <div className="feed-art-frame aspect-[16/10]">
        <CourseArt
          code={item.code}
          motif={item.illustration.motif}
          seed={item.illustration.seed}
          paletteIndex={item.illustration.palette}
          className="feed-art block h-full w-full"
        />
        <span className="glass absolute bottom-3 left-3 z-10 flex max-w-[75%] flex-col gap-0.5 rounded-[14px] bg-[rgb(12_5_8/0.62)] px-3 py-2 shadow-none">
          <span className="truncate font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-on-night-soft">{item.category.label}</span>
          <span className="truncate text-caption font-medium text-ink">{item.code}</span>
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-3 px-3 pb-3 pt-5">
        <ReasonChip>{item.reason}</ReasonChip>
        <h3 id={titleId} className="font-display text-[30px] leading-[1.08] tracking-[-0.3px] text-ink">
          <Link to={href} className="rounded-xs transition-colors duration-300 hover:text-primary-hover focus-visible:text-primary">
            {item.title}
          </Link>
        </h3>
        <Meta>
          <span className="font-mono text-[11.5px] uppercase tracking-[0.16em]">{item.code}</span>
          <span aria-hidden="true">·</span>
          <span>{item.units} units</span>
          {item.core_tags.length > 0 && (
            <>
              <span aria-hidden="true">·</span>
              <span>In the Core</span>
            </>
          )}
        </Meta>
        {item.excerpt && <p className="line-clamp-3 text-body-sm text-body">{item.excerpt}</p>}
        {rating}
        {stats && stats.n > 0 && (stats.workload_hours != null || stats.difficulty != null) && (
          <dl className="flex flex-wrap gap-2 text-caption">
            {stats.workload_hours != null && (
              <div className="qg-chip min-h-0 px-3 py-1.5">
                <dt className="qg-chip-label">Workload</dt>
                <dd className="qg-chip-value text-caption">{stats.workload_hours} h/week</dd>
              </div>
            )}
            {stats.difficulty != null && (
              <div className="qg-chip min-h-0 px-3 py-1.5">
                <dt className="qg-chip-label">Difficulty</dt>
                <dd className="qg-chip-value text-caption">{stats.difficulty} / 5</dd>
              </div>
            )}
            <div className="flex items-end px-1 pb-1.5 text-muted">
              <dt className="sr-only">Based on</dt>
              <dd>
                {stats.n} {stats.n === 1 ? "review" : "reviews"}
              </dd>
            </div>
          </dl>
        )}
        {item.commons_count > 0 && (
          // type=discussion: since issue #20 /forum also lists reviews; this link counts questions only.
          <Link to={`/forum?course=${encodeURIComponent(item.code)}&type=discussion`} className="inline-flex min-h-11 items-center self-start text-caption text-primary underline decoration-primary/40 underline-offset-[3px] hover:text-primary-hover">
            {item.commons_count} {item.commons_count === 1 ? "question" : "questions"} about it in the Forum
          </Link>
        )}
        <Link
          to={href}
          className="mt-auto inline-flex min-h-11 items-center gap-2 self-start rounded-pill text-button text-ink transition-colors hover:text-primary-hover"
          aria-label={`Open course ${item.code}`}
        >
          Open course
          <span aria-hidden="true" className="inline-flex size-8 items-center justify-center rounded-pill border border-hairline-strong transition-[translate,border-color] duration-300 group-hover:translate-x-1 group-hover:border-primary/60">
            <ArrowIcon size={14} />
          </span>
        </Link>
      </div>
    </article>
  );
}
