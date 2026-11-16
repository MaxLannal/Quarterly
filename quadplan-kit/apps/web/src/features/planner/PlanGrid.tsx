import { useDroppable } from "@dnd-kit/core";
import { useEffect, useId, useRef, useState } from "react";
import type { Goal, PlanItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { PencilIcon } from "@/components/ui/icons";
import { controlClass, controlCompactClass, Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { usePlanner } from "./context";
import { CourseCard } from "./CourseCard";
import { goalLabel, quarterMetrics, round1 } from "./metrics";
import { planYears, removeYear } from "./planModel";
import {
  academicYear,
  academicYearLabel,
  classYearLabel,
  graduationTerm,
  isBefore,
  MAX_PLAN_YEARS,
  planTerms,
  QUARTERS,
  resolveTermRef,
  termAt,
  termLabel,
} from "./terms";

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
        "flex min-h-24 min-w-0 flex-col rounded-lg border border-hairline bg-canvas-soft p-2 transition-[border-color,background-color,box-shadow] duration-200 sm:min-h-36",
        isOver && "border-primary bg-primary-wash shadow-hover",
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
          <span title="Difficulty index: the sum of course difficulty (1–5 each)">Difficulty {round1(m.difficulty)}</span>
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

/** The plan's name as the grid's heading, with a pencil to rename it (FEEDBACK 2026-11-16). */
function PlanName({ name, onRename }: { name: string; onRename: (name: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const input = useRef<HTMLInputElement>(null);
  const inputId = useId();
  useEffect(() => {
    if (editing) input.current?.select();
  }, [editing]);
  if (editing) {
    const commit = () => {
      const next = draft.trim();
      if (next && next !== name) onRename(next);
      setEditing(false);
    };
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          commit();
        }}
      >
        <label htmlFor={inputId} className="sr-only">
          Plan name
        </label>
        <Input
          ref={input}
          id={inputId}
          value={draft}
          maxLength={80}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setDraft(name);
              setEditing(false);
            }
          }}
          className="w-72 max-w-full font-display text-display-sm"
        />
      </form>
    );
  }
  return (
    <div className="flex min-w-0 items-center gap-1">
      <h2 className="truncate font-display text-display-sm sm:text-display-md">{name || "My Plan"}</h2>
      <button
        type="button"
        aria-label="Rename plan"
        onClick={() => {
          setDraft(name);
          setEditing(true);
        }}
        className="flex size-11 shrink-0 items-center justify-center rounded-md text-gray-dark transition-colors hover:bg-canvas-soft hover:text-ink"
      >
        <PencilIcon size={18} />
      </button>
    </div>
  );
}

/** Graduation choices: Autumn, Winter and Spring from the first quarter to one year past the
 * last, never past the longest plan the API accepts. */
function graduationChoices(entryTerm: string, years: number): string[] {
  const out: string[] = [];
  for (let y = 1; y <= Math.min(years + 1, MAX_PLAN_YEARS); y += 1) {
    for (const q of ["AU", "WI", "SP"] as const) {
      const t = termAt(entryTerm, y, q);
      if (!isBefore(t, entryTerm)) out.push(t);
    }
  }
  return out;
}

interface PlanGridProps {
  name: string;
  onRename: (name: string) => void;
  showSummer: boolean;
  onToggleSummer: () => void;
  onGraduation: (term: string) => void;
  onAddYear: () => void;
}

/**
 * The plan grid. Each academic year opens with its Summer (optional, hidden by default), then
 * Autumn, Winter and Spring (FEEDBACK F2). The grid ends at the graduation quarter (F3); items
 * outside it are listed under "Other terms".
 */
export function PlanGrid({ name, onRename, showSummer, onToggleSummer, onGraduation, onAddYear }: PlanGridProps) {
  const { plan } = usePlanner();
  const [yearMsg, setYearMsg] = useState<string | null>(null);
  const gradId = useId();
  const items = plan.items ?? [];
  const last = graduationTerm(plan);
  const years = planYears(plan);
  const level = plan.entry_year_level ?? 1;
  const terms = planTerms(plan.entry_term, last);
  const shown = new Set(terms);
  const byTerm = new Map<string, PlanItem[]>();
  for (const item of items) byTerm.set(item.term, [...(byTerm.get(item.term) ?? []), item]);
  const outside = items.filter((i) => !shown.has(i.term));
  const choices = graduationChoices(plan.entry_term, years);
  if (!choices.includes(last)) choices.push(last);

  function removeLastYear() {
    const r = removeYear(plan);
    if (!r.ok) {
      setYearMsg(r.error);
      return;
    }
    setYearMsg(null);
    if (r.plan.graduation_term) onGraduation(r.plan.graduation_term);
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <PlanName name={name} onRename={onRename} />
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label htmlFor={gradId} className="text-caption-uppercase uppercase text-muted">
              Graduating in
            </label>
            <select id={gradId} value={last} onChange={(e) => onGraduation(e.target.value)} className={cn(controlClass, controlCompactClass, "w-44")}>
              {choices.map((t) => (
                <option key={t} value={t}>
                  {termLabel(t)}
                </option>
              ))}
            </select>
          </div>
          <Button variant="outline" onClick={onToggleSummer} aria-pressed={showSummer}>
            {showSummer ? "Hide Summer" : "Show Summer"}
          </Button>
        </div>
      </div>
      {Array.from({ length: years }, (_, i) => i + 1).map((y) => {
        const start = academicYear(termAt(plan.entry_term, y, "AU"));
        const summer = termAt(plan.entry_term, y, "SU");
        const summerItems = byTerm.get(summer) ?? [];
        const yearTerms = QUARTERS.map((q) => termAt(plan.entry_term, y, q)).filter((t) => shown.has(t));
        const visible = yearTerms.filter((t) => showSummer || !t.endsWith("-SU"));
        return (
          <section key={y} aria-labelledby={`year-${y}`} data-testid={`year-${y}`}>
            <h3 id={`year-${y}`} className="mb-3 flex flex-wrap items-baseline gap-x-2 font-display text-display-sm">
              {classYearLabel(y, level)}{" "}
              <span className="font-sans text-caption tabular-nums text-muted">{academicYearLabel(start)}</span>
              {!showSummer && summerItems.length > 0 && (
                <span className="font-sans text-caption text-muted">
                  {" "}
                  · {termLabel(summer)}: {summerItems.length} course{summerItems.length === 1 ? "" : "s"} (hidden)
                </span>
              )}
            </h3>
            <div className={cn("grid grid-cols-1 gap-3 sm:grid-cols-3", showSummer && "xl:grid-cols-4")}>
              {visible.map((term) => (
                <QuarterCell key={term} term={term} items={byTerm.get(term) ?? []} />
              ))}
            </div>
          </section>
        );
      })}
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setYearMsg(null);
              onAddYear();
            }}
            disabled={years >= MAX_PLAN_YEARS}
          >
            Add a year
          </Button>
          <Button variant="ghost" onClick={removeLastYear} disabled={years <= 1}>
            Remove last year
          </Button>
        </div>
        <p role="status" className="text-caption text-error empty:hidden">
          {yearMsg}
        </p>
      </div>
      {outside.length > 0 && (
        <section aria-labelledby="other-terms" className="animate-fade-in">
          <h3 id="other-terms" className="font-display text-display-sm">
            Other terms
          </h3>
          <p className="text-body-sm text-muted">Outside the quarters above.</p>
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
