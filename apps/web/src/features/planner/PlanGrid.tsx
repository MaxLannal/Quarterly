import { useDroppable } from "@dnd-kit/core";
import { useEffect, useId, useState } from "react";
import type { Goal, PlanItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { GlassFolder, type FolderTone } from "@/components/ui/folder";
import { ErrorIcon, PlusIcon, WarningIcon } from "@/components/ui/icons";
import { Label } from "@/components/ui/input";
import { CoursePicker } from "@/features/courses/CoursePicker";
import { currentTerm } from "@/features/generate/deterministic";
import { cn } from "@/lib/utils";
import { issuesForItem, usePlanner } from "./context";
import { CourseCard } from "./CourseCard";
import { goalLabel, quarterMetrics, round1 } from "./metrics";
import { addCourseOps, planYears, removeYear } from "./planModel";
import "./planner.css";
import {
  academicYear,
  academicYearLabel,
  classYearLabel,
  graduationTerm,
  MAX_PLAN_YEARS,
  planTerms,
  QUARTERS,
  quarterStages,
  resolveTermRef,
  termAt,
  termLabel,
  type QuarterStage,
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

/** The folder's tone (docs/DESIGN.md "Dark glass"): the quarter in hand glows ember, Summer is
 * frosted glass, the rest are smoke (past quarters a little dimmer, planner.css). */
function toneFor(term: string, stage: QuarterStage): FolderTone {
  if (stage === "now" || stage === "next") return "ember";
  if (term.endsWith("-SU")) return "frost";
  return "smoke";
}

const STAGE_LABEL: Record<QuarterStage, string | null> = { now: "Now", next: "Next", past: "Past", ahead: null };

/** "+" on a folder: search the catalog and add a course straight to this quarter. */
function AddCourseDialog({ term, open, onClose }: { term: string; open: boolean; onClose: () => void }) {
  const { plan, edit } = usePlanner();
  const id = useId();
  // The dialog focuses its first control (Close); the search field is what the student came for.
  // This runs after the dialog's own focus effect (a parent's effects run after its children's).
  useEffect(() => {
    if (open) document.getElementById(id)?.focus();
  }, [open, id]);
  return (
    <Dialog open={open} onClose={onClose} title={`Add a course to ${termLabel(term)}`} description="Type a course code or name, then choose it from the list.">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={id}>Course</Label>
        <CoursePicker
          id={id}
          catalogYear={plan.catalog_year}
          value=""
          onChange={(code) => {
            if (!code) return;
            edit(addCourseOps(code, term));
            onClose();
          }}
        />
      </div>
      <p className="mt-4 text-caption text-muted">Courses that count toward your programs are listed under Requirements.</p>
    </Dialog>
  );
}

/**
 * One quarter: a glass folder whose files are the quarter's classes (Max, 2026-11-27). The tab
 * names the quarter; the pocket carries its totals, its issues and the "+" that adds a course.
 * The whole folder is the drop target, and lights red under a dragged file.
 */
function QuarterFolder({ term, items, stage }: { term: string; items: PlanItem[]; stage: QuarterStage }) {
  const { plan, courses, issues, highlight } = usePlanner();
  const { setNodeRef, isOver } = useDroppable({ id: term, data: { term } });
  const [adding, setAdding] = useState(false);
  const m = quarterMetrics(items, courses);
  const goals = termGoals(plan.goals ?? [], term, plan.entry_term);
  const mine = items.flatMap((i) => issuesForItem(issues, i));
  const errors = mine.filter((i) => i.level === "error").length;
  const warnings = mine.filter((i) => i.level === "warning").length;
  const headingId = `term-${term}`;
  const label = termLabel(term);
  const stageLabel = STAGE_LABEL[stage];
  return (
    <section ref={setNodeRef} aria-labelledby={headingId} data-testid={`quarter-${term}`} data-stage={stage} className="planner-quarter">
      <GlassFolder
        aside={
          stageLabel ? (
            <span className="planner-stage mono-label" data-stage={stage}>
              {stageLabel}
            </span>
          ) : undefined
        }
        tone={toneFor(term, stage)}
        active={isOver || highlight.terms.has(term)}
        tabRatio={0.6}
        className="h-full"
        bodyClassName="planner-folder-body"
        tab={
          <h4 id={headingId} className="planner-tab truncate font-display text-[22px] leading-none text-ink">
            {label}
          </h4>
        }
        pocket={
          <>
            {items.length > 0 ? (
              <div className="flex min-w-0 flex-1 flex-col justify-center gap-0.5" data-testid={`footer-${term}`}>
                <p className="mono-label truncate text-ink">
                  {m.units}
                  {m.unitsPartial ? "+" : ""} units
                  <span aria-hidden="true" className="px-1.5 text-muted">
                    ·
                  </span>
                  <span className="text-body">
                    {m.courses} course{m.courses === 1 ? "" : "s"}
                  </span>
                </p>
                <p className="truncate text-[13px] tabular-nums text-muted">
                  {round1(m.hours)}
                  {m.hoursPartial && m.courses ? "+" : ""} h/wk
                  <span aria-hidden="true"> · </span>
                  <span title="Difficulty index: the sum of course difficulty (1–5 each)">Difficulty {round1(m.difficulty)}</span>
                </p>
              </div>
            ) : (
              <span className="min-w-0 flex-1" />
            )}
            {(errors > 0 || warnings > 0) && (
              <p className="flex shrink-0 items-center gap-2 text-[13px] font-medium tabular-nums">
                {errors > 0 && (
                  <span className="inline-flex items-center gap-1 text-error">
                    <ErrorIcon size={14} />
                    {errors}
                    <span className="sr-only"> {errors === 1 ? "error" : "errors"}</span>
                  </span>
                )}
                {warnings > 0 && (
                  <span className="inline-flex items-center gap-1 text-warning">
                    <WarningIcon size={14} className="text-warning-icon" />
                    {warnings}
                    <span className="sr-only"> {warnings === 1 ? "warning" : "warnings"}</span>
                  </span>
                )}
              </p>
            )}
            <button type="button" className="planner-add" aria-label={`Add a course to ${label}`} aria-haspopup="dialog" onClick={() => setAdding(true)}>
              <PlusIcon size={18} />
            </button>
          </>
        }
      >
        {items.length === 0 ? (
          // PL-3 (D11): say what is there, not only how to drag.
          <p className="planner-empty">No courses yet</p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {items.map((item) => (
              <CourseCard key={item.id ?? `${item.course}-${item.term}`} item={item} />
            ))}
          </ul>
        )}
        {goals.length > 0 && (
          <ul className="mt-auto flex flex-wrap gap-1.5 pt-3" aria-label={`Goals for ${label}`}>
            {goals.map((g) => (
              <li key={g.id} className="planner-goal">
                {goalLabel(g)}
              </li>
            ))}
          </ul>
        )}
      </GlassFolder>
      <AddCourseDialog term={term} open={adding} onClose={() => setAdding(false)} />
    </section>
  );
}

interface PlanGridProps {
  showSummer: boolean;
  onToggleSummer: () => void;
  onGraduation: (term: string) => void;
  onAddYear: () => void;
}

/**
 * The plan grid: each academic year is a shelf of quarter folders. A year opens with its Summer
 * (optional, hidden by default), then Autumn, Winter and Spring (FEEDBACK F2). The grid ends at
 * the graduation quarter (F3); items outside it are listed under "Other terms".
 */
export function PlanGrid({ showSummer, onToggleSummer, onGraduation, onAddYear }: PlanGridProps) {
  const { plan } = usePlanner();
  const [yearMsg, setYearMsg] = useState<string | null>(null);
  const items = plan.items ?? [];
  const last = graduationTerm(plan);
  const years = planYears(plan);
  const level = plan.entry_year_level ?? 1;
  const terms = planTerms(plan.entry_term, last);
  const shown = new Set(terms);
  const byTerm = new Map<string, PlanItem[]>();
  for (const item of items) byTerm.set(item.term, [...(byTerm.get(item.term) ?? []), item]);
  const outside = items.filter((i) => !shown.has(i.term));
  const stages = quarterStages(
    terms.filter((t) => showSummer || !t.endsWith("-SU")),
    currentTerm(),
  );

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
    <div className="flex flex-col gap-12 @container">
      <div className="-mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="mono-label text-muted">
          {years} year{years === 1 ? "" : "s"}
          <span aria-hidden="true" className="px-2 text-muted">
            {"//"}
          </span>
          {showSummer ? "Summer, Autumn, Winter, Spring" : "Autumn, Winter, Spring"}
        </p>
        <Button variant="outline" size="sm" onClick={onToggleSummer} aria-pressed={showSummer}>
          {showSummer ? "Hide Summer" : "Show Summer"}
        </Button>
      </div>
      {Array.from({ length: years }, (_, i) => i + 1).map((y) => {
        const start = academicYear(termAt(plan.entry_term, y, "AU"));
        const summer = termAt(plan.entry_term, y, "SU");
        const summerItems = byTerm.get(summer) ?? [];
        const yearTerms = QUARTERS.map((q) => termAt(plan.entry_term, y, q)).filter((t) => shown.has(t));
        const visible = yearTerms.filter((t) => showSummer || !t.endsWith("-SU"));
        return (
          <section key={y} aria-labelledby={`year-${y}`} data-testid={`year-${y}`} className="planner-shelf">
            <div className="mb-6 flex flex-wrap items-baseline gap-x-5 gap-y-1">
              <h3 id={`year-${y}`} className="flex shrink-0 items-baseline gap-x-3 font-display text-display-sm">
                {classYearLabel(y, level)}{" "}
                <span className="mono-label tabular-nums text-muted">{academicYearLabel(start)}</span>
              </h3>
              <span aria-hidden="true" className="planner-rule" />
              {!showSummer && summerItems.length > 0 && (
                <span className="mono-label text-muted">
                  {termLabel(summer)}: {summerItems.length} course
                  {summerItems.length === 1 ? "" : "s"} (hidden)
                </span>
              )}
            </div>
            <div className={cn("planner-shelf-row grid grid-cols-1 gap-x-5 gap-y-8 @lg:grid-cols-3", showSummer && "@4xl:grid-cols-4")}>
              {visible.map((term) => (
                <QuarterFolder key={term} term={term} items={byTerm.get(term) ?? []} stage={stages.get(term) ?? "ahead"} />
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
          <div className="mb-2 flex items-baseline gap-5">
            <h3 id="other-terms" className="shrink-0 font-display text-display-sm">
              Other terms
            </h3>
            <span aria-hidden="true" className="planner-rule" />
          </div>
          <p className="text-body-sm text-muted">Outside the quarters above.</p>
          <ul className="mt-4 grid gap-3 @lg:grid-cols-3">
            {outside.map((item) => (
              <CourseCard key={item.id} item={item} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
