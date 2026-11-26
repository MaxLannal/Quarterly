import { useId, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { CourseCode, Spinner } from "@/components/ui/misc";
import { RatingLine } from "@/features/courses/RatingLine";
import type { CatalogBrowse, NewCourse, RatingSummary } from "./api";
import { courseHref } from "./api";
import { CourseSpotlightCard } from "./cards/CourseSpotlightCard";
import { ReasonChip } from "./cards/parts";
import { CommentCard } from "./cards/VoiceCards";
import "./feed.css";

type Ratings = Record<string, RatingSummary> | undefined;

/** One browse row: a heading and cards that scroll sideways (snapping), inside the page width. */
function Row({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="mt-10 first:mt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id={id} className="font-display text-display-sm text-ink">
          {title}
        </h2>
        {hint && <p className="text-caption text-muted">{hint}</p>}
      </div>
      <ul className="-mx-1 mt-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-1 pb-3">{children}</ul>
    </section>
  );
}

function Slot({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return <li className={wide ? "w-[min(84vw,22rem)] shrink-0 snap-start" : "w-[min(84vw,19rem)] shrink-0 snap-start"}>{children}</li>;
}

/** A newly released course: its code and title, why it counts as new, and the source that says so. */
function NewCourseCard({ course, rating }: { course: NewCourse; rating?: RatingSummary }) {
  return (
    <Card className="relative flex h-full flex-col gap-3">
      <ReasonChip>{course.reason}</ReasonChip>
      <Link
        to={courseHref(course.code)}
        className="flex flex-col gap-1 rounded-xs text-ink hover:[&>span:last-child]:underline"
      >
        <CourseCode>{course.code}</CourseCode> <span className="sr-only">·</span>{" "}
        <span className="text-title-md underline-offset-4">{course.title}</span>
      </Link>
      {course.excerpt && <p className="line-clamp-3 text-body-sm text-body">{course.excerpt}</p>}
      <RatingLine rating={rating} />
      <p className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
        <span>{course.units} units</span>
        {course.core_tags.length > 0 && <span>In the Core</span>}
      </p>
      {course.source_url && (
        // The quote that says the course is new, readable by keyboard and touch too.
        <details className="text-caption text-muted">
          <summary className="inline-flex min-h-11 cursor-pointer items-center text-primary">Why it is new</summary>
          {course.source_quote && <blockquote className="mt-1 border-l-2 border-hairline pl-3 italic">{course.source_quote}</blockquote>}
          <a href={course.source_url} className="mt-1 inline-flex min-h-11 items-center text-primary underline underline-offset-2" rel="noreferrer">
            Source
          </a>
        </details>
      )}
    </Card>
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
  if (isLoading) return <Spinner label="Loading the catalog" />;
  if (isError || !data) return null;
  const { new_courses: fresh, spotlights, quotes } = data;
  return (
    <div className="mt-10">
      {fresh.length > 0 && (
        <Row title="Newly released courses" hint={data.catalog_year ? `New in the ${data.catalog_year} catalog` : undefined}>
          {fresh.map((c) => (
            <Slot key={c.code}>
              <NewCourseCard course={c} rating={ratings?.[c.code]} />
            </Slot>
          ))}
        </Row>
      )}
      {spotlights.length > 0 && (
        <Row title="Course spotlights" hint="Picked for you, refreshed daily">
          {spotlights.map((item) => (
            <Slot key={item.id} wide>
              <CourseSpotlightCard item={item} rating={<RatingLine rating={ratings?.[item.code]} />} />
            </Slot>
          ))}
        </Row>
      )}
      {quotes.length > 0 && (
        <Row title="What students say">
          {quotes.map((item) => (
            <Slot key={item.id} wide>
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
