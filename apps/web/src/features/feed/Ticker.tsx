import { useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { courseHref } from "./api";
import { useReducedMotion } from "./hooks";

/**
 * A slow ticker of the feed's course titles under the hero. It pauses on hover and focus and has
 * its own pause button; with reduced motion it is a still row that scrolls sideways.
 */
export function Ticker({ courses }: { courses: { code: string; title: string }[] }) {
  const reduced = useReducedMotion();
  const [paused, setPaused] = useState(false);
  if (courses.length === 0) return <div aria-hidden="true" className="h-14 border-b border-hairline bg-surface-card" />;

  const row = (copy: number) =>
    courses.map((c) => (
      <li key={`${copy}-${c.code}`} className="flex shrink-0 items-center">
        <Link
          to={courseHref(c.code)}
          tabIndex={copy === 0 ? undefined : -1}
          className="inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-pill px-3 font-display text-[19px] font-light italic text-ink hover:text-primary"
        >
          <span className="not-italic font-sans text-caption-uppercase uppercase text-muted">{c.code}</span>
          {c.title}
        </Link>
        <span aria-hidden="true" className="px-2 text-primary">
          ✦
        </span>
      </li>
    ));

  if (reduced) {
    return (
      <section aria-label="Course titles in today's feed" className="border-b border-hairline bg-surface-card">
        <ul className="mx-auto flex max-w-content overflow-x-auto px-4 py-1.5 sm:px-6 lg:px-8">{row(0)}</ul>
      </section>
    );
  }
  const style = { "--duration": `${Math.max(courses.length * 5, 40)}s` } as CSSProperties;
  return (
    <section
      aria-label="Course titles in today's feed"
      className="feed-ticker relative flex items-center border-b border-hairline bg-surface-card"
      data-paused={paused}
    >
      <div className="min-w-0 flex-1 overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_6%,black_94%,transparent)]">
        <div className="feed-ticker-track flex w-max py-1.5" style={style}>
          <ul className="flex">{row(0)}</ul>
          <ul className="flex" aria-hidden="true">
            {row(1)}
          </ul>
        </div>
      </div>
      <button
        type="button"
        onClick={() => setPaused((p) => !p)}
        aria-pressed={paused}
        className={cn(
          "mr-2 inline-flex size-11 shrink-0 items-center justify-center rounded-pill hover:bg-surface-strong hover:text-ink",
          paused ? "bg-primary-wash text-primary" : "text-muted",
        )}
        aria-label="Pause the ticker"
      >
        {paused ? (
          <svg width={14} height={14} viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
            <path d="M7 4.5v15l12-7.5z" />
          </svg>
        ) : (
          <svg width={14} height={14} viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
            <rect x={6} y={4.5} width={4} height={15} rx={1} />
            <rect x={14} y={4.5} width={4} height={15} rx={1} />
          </svg>
        )}
      </button>
    </section>
  );
}
