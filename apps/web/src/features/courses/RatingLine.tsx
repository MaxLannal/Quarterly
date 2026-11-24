import type { components } from "@/api/schema";
import { cn } from "@/lib/utils";

type RatingSummary = components["schemas"]["RatingSummary"];

const fmt = (n: number | null | undefined) => (n == null ? "–" : n.toFixed(1));

/**
 * A course's student rating in one line, for the Catalog's results and browse rows (issue #19).
 * Ratings need a login, as on the course page (`CourseOverview`): the page passes a summary only
 * to a logged-in student. `undefined` while it loads draws nothing.
 */
export function RatingLine({ rating, className }: { rating: RatingSummary | undefined; className?: string }) {
  if (!rating) return null;
  const n = rating.n_reviews;
  return (
    <p className={cn("text-caption tabular-nums", n > 0 ? "text-ink" : "text-muted", className)}>
      <span className="sr-only">Student rating: </span>
      {n === 0 ? (
        "No reviews yet"
      ) : (
        <>
          <span className="font-semibold">{fmt(rating.overall)} / 5</span> · difficulty {fmt(rating.difficulty)} / 5 ·{" "}
          <span className="text-muted">
            {n} {n === 1 ? "review" : "reviews"}
          </span>
        </>
      )}
    </p>
  );
}
