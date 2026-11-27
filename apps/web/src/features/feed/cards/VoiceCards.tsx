/** A student's quote about a course (the Catalog's "What students say" row, issue #19). */
import { useId, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowIcon } from "@/components/ui/icons";
import { relativeDay } from "@/features/forum/format";
import type { CommentItem } from "../api";
import { CourseChip, Meta } from "./parts";

const VOICE: Record<CommentItem["voice"], string> = {
  reply: "Answer in the Forum",
  review: "Course review",
  discussion: "Discussion",
};

/** `rating`: the course's student rating line (logged in only), from the page. */
export function CommentCard({ item, rating }: { item: CommentItem; rating?: ReactNode }) {
  const id = useId();
  return (
    <article aria-labelledby={id} className="relative h-full overflow-hidden rounded-xl border border-hairline bg-surface-card p-6">
      <span aria-hidden="true" className="pointer-events-none absolute left-4 top-2 h-[84px] select-none overflow-hidden font-serif text-[132px] leading-[1] text-primary/25">
        &ldquo;
      </span>
      <h3 id={id} className="sr-only">
        A student on {item.course.code} {item.course.title}
      </h3>
      <blockquote className="relative mt-12 font-serif text-[21px] font-light italic leading-[1.35] text-ink">
        <p>{item.snippet}</p>
      </blockquote>
      <Meta>
        <span className="font-medium text-body-strong">{item.handle}</span>
        <span aria-hidden="true">·</span>
        <span>{VOICE[item.voice]}</span>
        <span aria-hidden="true">·</span>
        <span>{relativeDay(item.day)}</span>
      </Meta>
      <div className="mt-4 flex flex-col gap-3">
        <CourseChip code={item.course.code} title={item.course.title} />
        {rating}
        <Link to={item.href} className="inline-flex min-h-11 items-center gap-1.5 self-start text-button text-primary hover:text-primary-hover">
          Join the discussion <ArrowIcon size={14} />
        </Link>
      </div>
    </article>
  );
}
