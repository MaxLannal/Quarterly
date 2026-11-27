/** A student's quote about a course (the Catalog's "What students say" row, issue #19). */
import { useId, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowIcon } from "@/components/ui/icons";
import { relativeDay } from "@/features/forum/format";
import type { CommentItem } from "../api";
import { CourseChip } from "./parts";

const VOICE: Record<CommentItem["voice"], string> = {
  reply: "Answer in the Forum",
  review: "Course review",
  discussion: "Discussion",
};

/**
 * `rating`: the course's student rating line (logged in only), from the page.
 * Dark glass: a quiet pane with a glowing serif quote mark, the words in Newsreader italic, the
 * voice in mono beneath a hairline.
 */
export function CommentCard({ item, rating }: { item: CommentItem; rating?: ReactNode }) {
  const id = useId();
  return (
    <article aria-labelledby={id} data-spotlight="" className="qg-tile qg-tile-link group flex h-full flex-col p-7">
      <span aria-hidden="true" className="feed-quote-mark pointer-events-none -mb-12 -ml-1 block h-[72px] select-none">
        &ldquo;
      </span>
      <h3 id={id} className="sr-only">
        A student on {item.course.code} {item.course.title}
      </h3>
      <blockquote className="relative font-serif text-[22px] font-light italic leading-[1.4] text-ink">
        <p>{item.snippet}</p>
      </blockquote>
      <p className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-hairline pt-4 font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
        <span className="normal-case tracking-normal font-sans text-caption font-medium text-body-strong">{item.handle}</span>
        <span aria-hidden="true">//</span>
        <span>{VOICE[item.voice]}</span>
        <span aria-hidden="true">//</span>
        <span>{relativeDay(item.day)}</span>
      </p>
      <div className="mt-4 flex flex-1 flex-col gap-3">
        <CourseChip code={item.course.code} title={item.course.title} />
        {rating}
        <Link to={item.href} className="mt-auto inline-flex min-h-11 items-center gap-2 self-start text-button text-ink transition-colors hover:text-primary-hover">
          Join the discussion
          <span aria-hidden="true" className="inline-flex size-8 items-center justify-center rounded-pill border border-hairline-strong transition-[translate,border-color] duration-300 group-hover:translate-x-1 group-hover:border-primary/60">
            <ArrowIcon size={14} />
          </span>
        </Link>
      </div>
    </article>
  );
}
