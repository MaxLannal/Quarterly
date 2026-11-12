import { useDroppable } from "@dnd-kit/core";
import type { Goal, PlanItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { usePlanner } from "./context";
import { CourseCard } from "./CourseCard";
import { goalLabel, quarterMetrics, round1 } from "./metrics";
import { academicYear, QUARTERS, resolveTermRef, termAt, termLabel } from "./terms";

function termGoals(goals: Goal[], term: string, entryTerm: string): Goal[] {
  return goals.filter((g) => {
    if (g.scope !== "term" || !g.term) return false;
    try {
      return resolveTermRef(g.term, entryTerm) === term;
    } catch {
      return false;
    }
  });
}

function QuarterCell({ term, items }: { term: string; items: PlanItem[] }) {
  const { plan, courses, highlight } = usePlanner();
  const { setNodeRef, isOver } = useDroppable({ id: term, data: { term } });
  const m = quarterMetrics(items, courses);
  const goals = termGoals(plan.goals ?? [], term, plan.entry_term);
  const headingId = `term-${term}`;
  return (
    <section
      ref={setNodeRef}
      aria-labelledby={headingId}
      data-testid={`quarter-${term}`}
      className={cn(
        "flex min-h-28 min-w-0 flex-col rounded-lg sm:min-h-40 border border-border bg-muted/40 p-2",
        isOver && "border-blue-700 bg-blue-50",
        highlight.terms.has(term) && "ring-4 ring-blue-600",
      )}
    >
      <h4 id={headingId} className="mb-1 text-sm font-semibold">
        {termLabel(term)}
      </h4>
      {items.length === 0 ? (
        <p className="flex flex-1 items-center justify-center rounded-md border border-dashed border-zinc-400 p-2 text-center text-xs text-muted-foreground">
          Drop a course here
        </p>
      ) : (
        <ul className="flex flex-1 flex-col gap-1.5">
          {items.map((item) => (
            <CourseCard key={item.id ?? `${item.course}-${item.term}`} item={item} />
          ))}
        </ul>
      )}
      <footer className="mt-2 border-t border-border pt-1 text-xs text-muted-foreground" data-testid={`footer-${term}`}>
        <div className="flex flex-wrap gap-x-3">
          <span>
            {m.units}
            {m.unitsPartial ? "+" : ""} units
          </span>
          <span>
            {round1(m.hours)}
            {m.hoursPartial && m.courses ? "+" : ""} h/wk
          </span>
          <span title="Difficulty index: the sum of course difficulty (1–5 each)">
            Difficulty {round1(m.difficulty)}
          </span>
        </div>
        {goals.length > 0 && (
          <ul className="mt-1 flex flex-wrap gap-1" aria-label={`Goals for ${termLabel(term)}`}>
            {goals.map((g) => (
              <li key={g.id} className="rounded-full border border-blue-700 px-2 text-blue-900">
                {goalLabel(g)}
              </li>
            ))}
          </ul>
        )}
      </footer>
    </section>
  );
}

interface PlanGridProps {
  years: number;
  showSummer: boolean;
  onToggleSummer: () => void;
  onYears: (n: number) => void;
}

export function PlanGrid({ years, showSummer, onToggleSummer, onYears }: PlanGridProps) {
  const { plan } = usePlanner();
  const items = plan.items ?? [];
  const byTerm = new Map<string, PlanItem[]>();
  for (const item of items) byTerm.set(item.term, [...(byTerm.get(item.term) ?? []), item]);
  const shown = new Set<string>();
  const yearNums = Array.from({ length: years }, (_, i) => i + 1);
  for (const y of yearNums) for (const q of QUARTERS) shown.add(termAt(plan.entry_term, y, q));
  const outside = items.filter((i) => !shown.has(i.term));
  const year5Empty = QUARTERS.every((q) => !(byTerm.get(termAt(plan.entry_term, 5, q)) ?? []).length);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Four-year plan</h2>
        <Button variant="outline" onClick={onToggleSummer} aria-pressed={showSummer}>
          {showSummer ? "Hide Summer" : "Show Summer"}
        </Button>
      </div>
      {yearNums.map((y) => {
        const start = academicYear(termAt(plan.entry_term, y, "AU"));
        const summer = termAt(plan.entry_term, y, "SU");
        const summerItems = byTerm.get(summer) ?? [];
        return (
          <section key={y} aria-labelledby={`year-${y}`} data-testid={`year-${y}`}>
            <h3 id={`year-${y}`} className="mb-2 text-base font-semibold">
              Year {y} <span className="font-normal text-muted-foreground">({start}–{String((start + 1) % 100).padStart(2, "0")})</span>
              {!showSummer && summerItems.length > 0 && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  · {termLabel(summer)}: {summerItems.length} course{summerItems.length === 1 ? "" : "s"} (hidden)
                </span>
              )}
            </h3>
            <div className={cn("grid grid-cols-1 gap-2 sm:grid-cols-3", showSummer && "xl:grid-cols-4")}>
              {QUARTERS.filter((q) => showSummer || q !== "SU").map((q) => {
                const term = termAt(plan.entry_term, y, q);
                return <QuarterCell key={term} term={term} items={byTerm.get(term) ?? []} />;
              })}
            </div>
          </section>
        );
      })}
      <div className="flex flex-wrap gap-2">
        {years < 5 ? (
          <Button variant="outline" onClick={() => onYears(5)}>
            Add Year 5
          </Button>
        ) : (
          year5Empty && (
            <Button variant="outline" onClick={() => onYears(4)}>
              Remove Year 5
            </Button>
          )
        )}
      </div>
      {outside.length > 0 && (
        <section aria-labelledby="other-terms">
          <h3 id="other-terms" className="text-base font-semibold">
            Other terms
          </h3>
          <p className="text-sm text-muted-foreground">These items are outside the grid&apos;s years.</p>
          <ul className="mt-2 grid gap-1.5 sm:grid-cols-3">
            {outside.map((item) => (
              <CourseCard key={item.id} item={item} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
