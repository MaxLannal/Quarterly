/** Cards for people and programs: a student's comment, an open question, a program spotlight. */
import { useId } from "react";
import { Link } from "react-router-dom";
import { ArrowIcon } from "@/components/ui/icons";
import { relativeDay } from "@/features/forum/format";
import type { CommentItem, ProgramItem, QuestionItem } from "../api";
import { AiNote, CourseChip, Meta } from "./parts";

const VOICE: Record<CommentItem["voice"], string> = {
  reply: "Answer in the Forum",
  review: "Course review",
  discussion: "Discussion",
};

export function CommentCard({ item, note }: { item: CommentItem; note?: string }) {
  const id = useId();
  return (
    <article aria-labelledby={id} className="relative overflow-hidden rounded-xl border border-hairline bg-surface-card p-6">
      <span aria-hidden="true" className="pointer-events-none absolute left-4 top-2 h-[84px] select-none overflow-hidden font-display text-[132px] leading-[1] text-primary/25">
        &ldquo;
      </span>
      <h3 id={id} className="sr-only">
        A student on {item.course.code} {item.course.title}
      </h3>
      <blockquote className="relative mt-12 font-display text-[21px] font-light italic leading-[1.35] text-ink">
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
        {note && <AiNote note={note} />}
        <Link to={item.href} className="inline-flex min-h-11 items-center gap-1.5 self-start text-button text-primary hover:text-primary-hover">
          Join the discussion <ArrowIcon size={14} />
        </Link>
      </div>
    </article>
  );
}

export function QuestionCard({ item, note }: { item: QuestionItem; note?: string }) {
  const id = useId();
  return (
    <article aria-labelledby={id} className="rounded-xl border border-dashed border-hairline-strong bg-canvas-soft p-6">
      <p className="flex items-center gap-2 text-caption-uppercase uppercase text-primary">
        <span aria-hidden="true" className="grid size-6 place-items-center rounded-pill bg-primary font-display text-[15px] normal-case text-on-primary">
          ?
        </span>
        Can you help?
      </p>
      <h3 id={id} className="mt-3 font-display text-[22px] font-light leading-tight text-ink">
        <Link to={item.href} className="rounded-xs hover:text-primary">
          {item.title}
        </Link>
      </h3>
      {item.snippet && <p className="mt-2 line-clamp-3 text-body-sm text-body">{item.snippet}</p>}
      <div className="mt-3 flex flex-col gap-3">
        {item.course && <CourseChip code={item.course.code} title={item.course.title} />}
        <Meta>
          <span>{item.reply_count === 0 ? "No answers yet" : `${item.reply_count} ${item.reply_count === 1 ? "answer" : "answers"}`}</span>
          <span aria-hidden="true">·</span>
          <span>asked {relativeDay(item.day)}</span>
        </Meta>
        {note && <AiNote note={note} />}
        <Link to={item.href} className="inline-flex min-h-11 items-center gap-1.5 self-start text-button text-primary hover:text-primary-hover">
          Answer in the Forum <ArrowIcon size={14} />
        </Link>
      </div>
    </article>
  );
}

const PROGRAM_TYPE: Record<string, string> = {
  major: "Major",
  minor: "Minor",
  core: "General education",
  bxms: "Joint bachelor's and master's",
  study_abroad_block: "Study abroad",
};

export function ProgramCard({ item, note }: { item: ProgramItem; note?: string }) {
  const id = useId();
  return (
    <article aria-labelledby={id} className="relative isolate overflow-hidden rounded-xl border border-hairline bg-surface-card p-6">
      <svg aria-hidden="true" viewBox="0 0 200 120" className="pointer-events-none absolute -right-6 -top-4 -z-10 h-32 w-52 text-primary/15">
        {[0, 1, 2, 3, 4].map((k) => (
          <path key={k} d={`M0,${110 - k * 18} C60,${70 - k * 18} 120,${130 - k * 18} 200,${80 - k * 18}`} fill="none" stroke="currentColor" strokeWidth={6} />
        ))}
      </svg>
      <p className="text-caption-uppercase uppercase text-muted">{PROGRAM_TYPE[item.type] ?? "Program"}</p>
      <h3 id={id} className="mt-2 font-display text-[24px] font-light leading-tight text-ink">
        <Link to={`/programs/${encodeURIComponent(item.program_id)}`} className="rounded-xs hover:text-primary">
          {item.name}
        </Link>
      </h3>
      {item.department && <p className="mt-1 text-caption text-muted">{item.department}</p>}
      <p className="mt-3 text-body-sm text-body">{item.reason}</p>
      {note && (
        <div className="mt-3">
          <AiNote note={note} />
        </div>
      )}
      <Link
        to={`/programs/${encodeURIComponent(item.program_id)}`}
        className="mt-2 inline-flex min-h-11 items-center gap-1.5 text-button text-primary hover:text-primary-hover"
      >
        Explore the program <ArrowIcon size={14} />
      </Link>
    </article>
  );
}

export function SkeletonCard({ tall = false }: { tall?: boolean }) {
  return (
    <div aria-hidden="true" className="overflow-hidden rounded-xl border border-hairline bg-surface-card">
      {tall && <div className="feed-skeleton skeleton aspect-[16/10] rounded-none" />}
      <div className="flex flex-col gap-3 p-6">
        <div className="feed-skeleton skeleton h-6 w-40 rounded-pill" />
        <div className="feed-skeleton skeleton h-7 w-4/5" />
        <div className="feed-skeleton skeleton h-4 w-full" />
        <div className="feed-skeleton skeleton h-4 w-11/12" />
        <div className="feed-skeleton skeleton h-4 w-2/3" />
      </div>
    </div>
  );
}
