/**
 * The planner panel's other views (issue #18): a course's details with the student ratings
 * (step 15), and the edit history with a Revert on each edit (step 16). Both return to the chat.
 */
import { useCourse } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/layout/page";
import { CourseOverview } from "@/features/courses/CourseOverview";
import { RatingLine } from "@/features/courses/RatingLine";
import { useCourseRatings } from "@/features/feed/api";
import { useSession } from "@/lib/session";
import type { HistoryEntry } from "./history";

function Header({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className="flex items-center gap-2 border-b border-hairline px-4 py-3">
      <Button variant="ghost" onClick={onBack} aria-label="Back to the chat">
        <span aria-hidden="true">← Chat</span>
      </Button>
      <h2 className="font-display text-title-lg">{title}</h2>
    </header>
  );
}

export function DetailsPanel({ code, catalogYear, onBack }: { code: string; catalogYear: string; onBack: () => void }) {
  const course = useCourse(code, catalogYear);
  const { data: session } = useSession();
  const ratings = useCourseRatings(session?.account.id ?? null, [code]);
  return (
    <section aria-label="Course details" className="flex min-h-0 flex-1 flex-col">
      <Header title="Course details" onBack={onBack} />
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <h3 className="font-display text-title-md tabular-nums">
          {code}
          {course.data?.title ? <span className="font-sans text-body text-muted"> · {course.data.title}</span> : null}
        </h3>
        {session && <RatingLine rating={ratings.data?.[code]} />}
        {course.isLoading ? <LoadingState label="Loading the course" /> : course.data ? <CourseOverview course={course.data} /> : <p className="text-body-sm text-muted">This course is not in the catalog.</p>}
      </div>
    </section>
  );
}

export function HistoryPanel({ entries, onRevert, onBack }: { entries: readonly HistoryEntry[]; onRevert: (entry: HistoryEntry) => void; onBack: () => void }) {
  return (
    <section aria-label="Edit history" className="flex min-h-0 flex-1 flex-col">
      <Header title="Edit history" onBack={onBack} />
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {entries.length === 0 ? (
          <p className="text-body-sm text-muted">No edits yet. Each change to your plan shows here, with a Revert button.</p>
        ) : (
          <ol className="flex flex-col gap-2">
            {entries.map((e) => (
              <li key={e.id} className="flex items-center gap-3 rounded-lg border border-hairline bg-surface-card px-3 py-2 text-body-sm">
                <div className="min-w-0 flex-1">
                  <p className="text-ink">{e.label}</p>
                  <p className="text-caption tabular-nums text-muted">{e.day}</p>
                </div>
                <Button variant="outline" size="sm" onClick={() => onRevert(e)} disabled={e.inverse.length === 0}>
                  Revert
                </Button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
