import { useDroppable } from "@dnd-kit/core";
import type { Goal, PlanItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/misc";
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
        "flex min-h-28 min-w-0 flex-col rounded-xl border border-hairline bg-canvas-soft p-3 transition-colors sm:min-h-44",
        isOver && "border-primary bg-primary-wash",
        highlight.terms.has(term) && "ring-2 ring-primary ring-offset-2 ring-offset-canvas",
      )}
    >
      <h4 id={headingId} className="mb-2 text-caption-uppercase uppercase text-muted">
        {termLabel(term)}
      </h4>
      {items.length === 0 ? (
        <p className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-hairline-strong p-3 text-center text-caption text-muted">
          Drop a course here
        </p>
      ) : (
        <ul className="flex flex-1 flex-col gap-2">
          {items.map((item) => (
            <CourseCard key={item.id ?? `${item.course}-${item.term}`} item={item} />
          ))}
        </ul>
      )}
      <footer className="mt-3 border-t border-hairline pt-2 text-caption tabular-nums text-muted" data-testid={`footer-${term}`}>
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
          <ul className="mt-2 flex flex-wrap gap-1" aria-label={`Goals for ${termLabel(term)}`}>
            {goals.map((g) => (
              <li key={g.id}>
                <Badge casing="normal" className="py-0.5">
                  {goalLabel(g)}
                </Badge>
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
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-display-sm sm:text-display-md">Four-year plan</h2>
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
            <h3 id={`year-${y}`} className="mb-3 font-display text-display-sm">
              Year {y} <span className="font-sans text-caption tabular-nums text-muted">({start}–{String((start + 1) % 100).padStart(2, "0")})</span>
              {!showSummer && summerItems.length > 0 && (
                <span className="ml-2 font-sans text-caption text-muted">
                  · {termLabel(summer)}: {summerItems.length} course{summerItems.length === 1 ? "" : "s"} (hidden)
                </span>
              )}
            </h3>
            <div className={cn("grid grid-cols-1 gap-3 sm:grid-cols-3", showSummer && "xl:grid-cols-4")}>
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
          <h3 id="other-terms" className="font-display text-display-sm">
            Other terms
          </h3>
          <p className="text-body-sm text-muted">These items are outside the grid&apos;s years.</p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-3">
            {outside.map((item) => (
              <CourseCard key={item.id} item={item} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
