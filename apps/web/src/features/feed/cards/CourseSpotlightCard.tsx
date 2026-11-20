import { useCallback, useId, useMemo, useRef, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { ArrowIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { courseHref, type CourseItem } from "../api";
import { BookCover } from "../art/BookCover";
import { CourseArt } from "../art/CourseArt";
import { rng } from "../art/rng";
import { useInView, useReducedMotion, useRegisterWords } from "../hooks";
import { AiNote, BookmarkIcon, CardAction, LessIcon, Meta, ReasonChip } from "./parts";

const BURST_MS = 2200;

/** Where each keyword flies when the card is hovered or focused (stable per course). */
function burstPaths(seed: number, n: number) {
  const r = rng(seed ^ 0x5bd1e995);
  return Array.from({ length: n }, (_, i) => {
    const side = i % 2 ? 1 : -1;
    return {
      x: `${Math.round(18 + r() * 64)}%`,
      y: `${Math.round(30 + r() * 50)}%`,
      dx: `${Math.round(side * (24 + r() * 90))}px`,
      dy: `${Math.round(-(46 + r() * 90))}px`,
      rot: `${Math.round(side * r() * 12)}deg`,
    };
  });
}

/**
 * A course spotlight: generated art with the code set into it, the title, an excerpt of the
 * catalog description, why it is here (and the AI's note when there is one), books from the
 * shelf, review stats, and Save / Show less. On hover or focus its keywords lift off the art.
 */
export function CourseSpotlightCard({
  item,
  note,
  saved,
  onToggleSave,
  onLess,
}: {
  item: CourseItem;
  note?: string;
  saved: boolean;
  onToggleSave: () => void;
  onLess: () => void;
}) {
  const titleId = useId();
  const reduced = useReducedMotion();
  const [viewRef, inView] = useInView<HTMLElement>("0px");
  useRegisterWords(item.id, item.words, inView && !reduced);
  const [burst, setBurst] = useState(0);
  const last = useRef(0);
  const paths = useMemo(() => burstPaths(item.illustration.seed, item.words.length), [item.illustration.seed, item.words.length]);
  const lift = useCallback(() => {
    if (reduced) return;
    const now = Date.now();
    if (now - last.current < BURST_MS) return;
    last.current = now;
    setBurst(now);
  }, [reduced]);
  const href = courseHref(item.code);
  const stats = item.stats;

  return (
    <article
      ref={viewRef}
      aria-labelledby={titleId}
      onMouseEnter={lift}
      onFocus={lift}
      className="feed-spotlight group relative overflow-hidden rounded-xl border border-hairline bg-surface-card transition-shadow hover:shadow-hover focus-within:shadow-hover"
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
        {burst > 0 && !reduced && (
          <div key={burst} aria-hidden="true" className="pointer-events-none absolute inset-0">
            {item.words.map((word, i) => {
              const p = paths[i]!;
              const style = { "--x": p.x, "--y": p.y, "--dx": p.dx, "--dy": p.dy, "--rot": p.rot, "--i": i } as CSSProperties;
              return (
                <span
                  key={word}
                  style={style}
                  className={cn(
                    "feed-burst-word rounded-pill px-2.5 py-0.5 font-serif text-[18px] italic shadow-overlay",
                    i % 3 === 0 ? "bg-primary text-on-primary" : "bg-surface-card text-ink",
                  )}
                >
                  {word}
                </span>
              );
            })}
          </div>
        )}
      </div>
      <div className="flex flex-col gap-3 p-5 sm:p-6">
        <ReasonChip>{item.reason}</ReasonChip>
        <h3 id={titleId} className="font-display text-[26px] font-bold leading-[1.12] tracking-[-0.3px] text-ink">
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
        {item.excerpt && <p className="line-clamp-5 text-body-sm text-body">{item.excerpt}</p>}
        {note && <AiNote note={note} />}
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
        {item.books.length > 0 && (
          <section aria-label="From the Quarterly shelf" className="rounded-lg bg-canvas-soft p-3">
            <p className="text-caption-uppercase uppercase text-muted">From the Quarterly shelf</p>
            <ul className="mt-2 flex flex-col gap-2">
              {item.books.map((b) => (
                <li key={b.id} className="flex items-center gap-3">
                  <BookCover title={b.title} author={b.author} slug={b.slug} size="sm" className="h-[54px] w-9 shrink-0 rounded-xs shadow-hover" />
                  <span className="min-w-0 text-caption leading-snug">
                    <cite className="font-sans text-[15px] font-semibold not-italic text-ink">{b.title}</cite>
                    <span className="block text-muted">
                      {b.author}, {b.when}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-caption text-muted">Reading for the curious, not a syllabus.</p>
          </section>
        )}
        {item.commons_count > 0 && (
          <Link to={`/forum?course=${encodeURIComponent(item.code)}`} className="text-caption text-primary underline underline-offset-2">
            {item.commons_count} {item.commons_count === 1 ? "question" : "questions"} about it in the Forum
          </Link>
        )}
        <div className="-mx-2 mt-1 flex flex-wrap items-center justify-between gap-1">
          <Link
            to={href}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-pill px-2 text-button text-primary hover:text-primary-hover"
            aria-label={`Open course ${item.code}`}
          >
            Open course <ArrowIcon size={14} />
          </Link>
          <span className="flex items-center">
            <CardAction pressed={saved} onClick={onToggleSave} label={saved ? `Saved: ${item.code}` : `Save ${item.code}`}>
              <BookmarkIcon filled={saved} /> {saved ? "Saved" : "Save"}
            </CardAction>
            <CardAction onClick={onLess} label={`Less like this: ${item.code}, ${item.category.label}`}>
              <LessIcon /> Less like this
            </CardAction>
          </span>
        </div>
      </div>
    </article>
  );
}
