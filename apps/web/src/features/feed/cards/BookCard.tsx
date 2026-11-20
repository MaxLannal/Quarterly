import { useId } from "react";
import type { BookItem } from "../api";
import { BookCover } from "../art/BookCover";
import { AiNote, CourseChip, ReasonChip } from "./parts";

/** A book from the Quarterly shelf with the real courses that share its themes. */
export function BookCard({ item, note }: { item: BookItem; note?: string }) {
  const id = useId();
  const b = item.book;
  return (
    <article aria-labelledby={id} className="group rounded-xl border border-hairline bg-surface-card p-6">
      <p className="text-caption-uppercase uppercase text-muted">From the Quarterly shelf</p>
      <div className="mt-4 flex gap-5">
        <div className="relative shrink-0 [perspective:600px]">
          <BookCover
            title={b.title}
            author={b.author}
            slug={b.slug}
            className="h-[168px] w-28 rounded-sm shadow-overlay transition-transform duration-500 [transform-origin:left_center] group-hover:[transform:rotateY(-14deg)]"
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <h3 id={id} className="font-display text-[23px] font-bold leading-tight text-ink tracking-[-0.02em]">
            <cite className="not-italic">{b.title}</cite>
          </h3>
          <p className="text-body-sm text-body">{b.author}</p>
          <p className="text-caption text-muted">{b.when}</p>
          <p className="mt-2 text-caption text-muted">Reading for the curious, not a syllabus.</p>
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-3">
        <ReasonChip>{item.reason}</ReasonChip>
        {note && <AiNote note={note} />}
        <div>
          <p className="text-caption text-muted">Courses that share its themes</p>
          <ul className="mt-2 flex flex-wrap gap-1">
            {item.courses.map((c) => (
              <li key={c.code} className="max-w-full">
                <CourseChip code={c.code} title={c.title} />
              </li>
            ))}
          </ul>
        </div>
      </div>
    </article>
  );
}
