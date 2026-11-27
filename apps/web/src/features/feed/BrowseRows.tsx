import { useId, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowIcon } from "@/components/ui/icons";
import { Spinner } from "@/components/ui/misc";
import { Kicker } from "@/features/courses/Glass";
import { RatingLine } from "@/features/courses/RatingLine";
import type { CatalogBrowse, NewCourse, RatingSummary } from "./api";
import { courseHref } from "./api";
import { CourseSpotlightCard } from "./cards/CourseSpotlightCard";
import { ReasonChip } from "./cards/parts";
import { CommentCard } from "./cards/VoiceCards";
import "./feed.css";

type Ratings = Record<string, RatingSummary> | undefined;

/** Scroll a row by most of its width; instant under reduced motion. */
function scrollRow(el: HTMLElement | null, dir: 1 | -1) {
  if (!el) return;
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: reduce ? "auto" : "smooth" });
}

/**
 * One browse row, set like a magazine section: a mono index and kicker over the serif heading,
 * the hint on the right with two glass arrows, then cards that scroll sideways and snap.
 */
function Row({ index, kicker, title, hint, children }: { index: number; kicker: string; title: string; hint?: string; children: ReactNode }) {
  const id = useId();
  const list = useRef<HTMLUListElement>(null);
  return (
    <section aria-labelledby={id} className="feed-row mt-20 first:mt-0">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b border-hairline pb-5">
        <div className="flex min-w-0 flex-col gap-2">
          <Kicker>
            {String(index).padStart(2, "0")} <span className="text-muted-soft">//</span> {kicker}
          </Kicker>
          <h2 id={id} className="font-display text-display-sm text-ink sm:text-display-md">
            {title}
          </h2>
        </div>
        <div className="flex items-center gap-3">
          {hint && <p className="text-caption text-muted">{hint}</p>}
          <div className="hidden gap-1 sm:flex">
            <button type="button" aria-label={`Scroll ${title} back`} onClick={() => scrollRow(list.current, -1)} className="feed-arrow">
              <ArrowIcon size={16} className="rotate-180" />
            </button>
            <button type="button" aria-label={`Scroll ${title} forward`} onClick={() => scrollRow(list.current, 1)} className="feed-arrow">
              <ArrowIcon size={16} />
            </button>
          </div>
        </div>
      </div>
      <ul ref={list} className="qg-snap mt-7">
        {children}
      </ul>
    </section>
  );
}

function Slot({ children, wide = false, i = 0 }: { children: ReactNode; wide?: boolean; i?: number }) {
  return (
    <li className={wide ? "qg-rise w-[min(84vw,23rem)] shrink-0" : "qg-rise w-[min(84vw,20rem)] shrink-0"} style={{ ["--i" as string]: i }}>
      {children}
    </li>
  );
}

/** A newly released course: its code and title, why it counts as new, and the source that says so. */
function NewCourseCard({ course, rating }: { course: NewCourse; rating?: RatingSummary }) {
  const [subject = course.code, number = ""] = course.code.split(" ");
  return (
    <div data-spotlight="" className="qg-tile qg-tile-link qg-edge flex h-full flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-3">
        <span aria-hidden="true" className="flex flex-col">
          <span className="font-mono text-[10.5px] font-medium uppercase tracking-[0.2em] text-muted">{subject}</span>
          <span className="qg-numeral text-[44px]">{number}</span>
        </span>
        <ReasonChip>{course.reason}</ReasonChip>
      </div>
      <Link
        to={courseHref(course.code)}
        className="flex flex-col gap-1 rounded-xs text-ink hover:[&>span:last-child]:text-primary-hover"
      >
        <span className="sr-only">{course.code}</span> <span className="sr-only">·</span>{" "}
        <span className="text-title-md transition-colors duration-300">{course.title}</span>
      </Link>
      {course.excerpt && <p className="line-clamp-3 text-body-sm text-body">{course.excerpt}</p>}
      <RatingLine rating={rating} />
      <p className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11.5px] uppercase tracking-[0.16em] text-muted">
        <span>{course.units} units</span>
        {course.core_tags.length > 0 && <span>In the Core</span>}
      </p>
      {course.source_url && (
        // The quote that says the course is new, readable by keyboard and touch too.
        <details className="group border-t border-hairline pt-1 text-caption text-muted">
          <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 text-primary [&::-webkit-details-marker]:hidden">
            <span aria-hidden="true" className="transition-transform duration-300 group-open:rotate-90">›</span>
            Why it is new
          </summary>
          {course.source_quote && <blockquote className="mt-1 border-l border-primary/50 pl-3 font-serif text-body-sm italic text-body">{course.source_quote}</blockquote>}
          <a href={course.source_url} className="mt-1 inline-flex min-h-11 items-center text-primary underline underline-offset-2" rel="noreferrer">
            Source
          </a>
        </details>
      )}
    </div>
  );
}

/**
 * The Catalog's browse rows, shown before the student searches (issue #19): newly released
 * courses (when any are known), course spotlights and what students say. The spotlights and the
 * quotes come from the old Feed with their rules: forum reviews only for a logged-in reader;
 * ratings (`ratings`) only for a logged-in student.
 */
export function BrowseRows({
  data,
  isLoading,
  isError,
  ratings,
}: {
  data: CatalogBrowse | undefined;
  isLoading: boolean;
  isError: boolean;
  ratings: Ratings;
}) {
  if (isLoading) return <div className="mt-16"><Spinner label="Loading the catalog" /></div>;
  if (isError || !data) return null;
  const { new_courses: fresh, spotlights, quotes } = data;
  let n = 0;
  return (
    <div className="mt-20 sm:mt-24">
      {fresh.length > 0 && (
        <Row index={++n} kicker="New this year" title="Newly released courses" hint={data.catalog_year ? `New in the ${data.catalog_year} catalog` : undefined}>
          {fresh.map((c, i) => (
            <Slot key={c.code} i={i}>
              <NewCourseCard course={c} rating={ratings?.[c.code]} />
            </Slot>
          ))}
        </Row>
      )}
      {spotlights.length > 0 && (
        <Row index={++n} kicker="Spotlight" title="Course spotlights" hint="Picked for you, refreshed daily">
          {spotlights.map((item, i) => (
            <Slot key={item.id} wide i={i}>
              <CourseSpotlightCard item={item} rating={<RatingLine rating={ratings?.[item.code]} />} />
            </Slot>
          ))}
        </Row>
      )}
      {quotes.length > 0 && (
        <Row index={++n} kicker="Voices" title="What students say">
          {quotes.map((item, i) => (
            <Slot key={item.id} wide i={i}>
              <CommentCard item={item} rating={<RatingLine rating={ratings?.[item.course.code]} />} />
            </Slot>
          ))}
        </Row>
      )}
    </div>
  );
}

/** The codes whose ratings the rows show. */
export function browseCodes(data: CatalogBrowse | undefined): string[] {
  if (!data) return [];
  return [...data.new_courses.map((c) => c.code), ...data.spotlights.map((s) => s.code), ...data.quotes.map((q) => q.course.code)];
}
