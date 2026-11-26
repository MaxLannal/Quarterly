import { useDroppable } from "@dnd-kit/core";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { Goal, PlanItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { PencilIcon } from "@/components/ui/icons";
import {
  controlClass,
  controlCompactClass,
  Input,
} from "@/components/ui/input";
import { Badge } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { usePlanner } from "./context";
import { ProposalBlock } from "@/features/planner-agent/ProposalBlock";
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
  const { plan, courses, highlight, proposals } = usePlanner();
  const proposed = (proposals.get(term) ?? []).filter((b) => b.action !== "remove");
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
        highlight.terms.has(term) &&
          "ring-2 ring-primary ring-offset-2 ring-offset-canvas",
      )}
    >
      <h4
        id={headingId}
        className="mb-2 text-caption-uppercase uppercase text-muted"
      >
        {termLabel(term)}
      </h4>
      {items.length === 0 && proposed.length === 0 ? (
        // PL-3 (D11): say what is there, not only how to drag.
        <p className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-hairline-strong p-3 text-center text-caption text-muted">
          No courses yet
        </p>
      ) : (
        <ul className="flex flex-1 flex-col gap-2">
          {items.map((item) => (
            <CourseCard
              key={item.id ?? `${item.course}-${item.term}`}
              item={item}
            />
          ))}
          {proposed.map((b) => (
            <ProposalBlock key={`${b.proposalId}-${b.course}`} block={b} />
          ))}
        </ul>
      )}
      {/* PL-3 (D11): an empty quarter shows no row of zeros; the footer stays for its goals. */}
      {(items.length > 0 || goals.length > 0) && (
      <footer
        className="mt-3 border-t border-hairline pt-2 text-caption tabular-nums text-muted"
        data-testid={`footer-${term}`}
      >
        {items.length > 0 && (
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
        )}
        {goals.length > 0 && (
          <ul
            className="mt-2 flex flex-wrap gap-1"
            aria-label={`Goals for ${termLabel(term)}`}
          >
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
      )}
    </section>
  );
}

/** The plan's name as the grid's heading, with a pencil to rename it (FEEDBACK 2026-11-16). */
function PlanName({
  name,
  onRename,
}: {
  name: string;
  onRename: (name: string) => void;
}) {
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
      <h2 className="truncate font-display text-display-sm sm:text-display-md">
        {name || "My Plan"}
      </h2>
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

/**
 * The graduation quarter as a quiet line of text with a pencil, like the plan's name (D8, FEEDBACK
 * "Minor design changes"). The pencil opens the quarter list in place; choosing one applies it,
 * Escape or leaving the list keeps the old one.
 */
function GraduationField({
  value,
  choices,
  onChange,
}: {
  value: string;
  choices: string[];
  onChange: (term: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const selectId = useId();
  const select = useRef<HTMLSelectElement>(null);
  const pencil = useRef<HTMLButtonElement>(null);
  const wasEditing = useRef(false);
  useEffect(() => {
    if (editing) select.current?.focus();
    else if (wasEditing.current) pencil.current?.focus();
    wasEditing.current = editing;
  }, [editing]);
  if (editing) {
    return (
      <div className="flex items-center gap-2 text-caption text-muted">
        <label htmlFor={selectId}>Graduating in</label>
        <select
          ref={select}
          id={selectId}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setEditing(false);
          }}
          onBlur={() => setEditing(false)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setEditing(false);
          }}
          className={cn(controlClass, controlCompactClass, "w-40 text-caption pointer-coarse:text-body-md")}
        >
          {choices.map((t) => (
            <option key={t} value={t}>
              {termLabel(t)}
            </option>
          ))}
        </select>
      </div>
    );
  }
  return (
    <div
      className="flex items-center text-caption text-muted"
      data-testid="graduation"
      data-term={value}
    >
      <span>
        Graduating in{" "}
        <span className="font-medium text-body-strong">{termLabel(value)}</span>
      </span>
      <button
        ref={pencil}
        type="button"
        aria-label={`Change graduation quarter (${termLabel(value)})`}
        onClick={() => setEditing(true)}
        className="flex size-11 shrink-0 items-center justify-center rounded-md text-gray-dark transition-colors hover:bg-canvas-soft hover:text-ink"
      >
        <PencilIcon size={15} />
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
  /** The plan check's verdict, shown beside the name (PL-1, D11). */
  verdict?: ReactNode;
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
export function PlanGrid({
  name,
  verdict,
  onRename,
  showSummer,
  onToggleSummer,
  onGraduation,
  onAddYear,
}: PlanGridProps) {
  const { plan, proposals, openSummers, setSummerOpen } = usePlanner();
  const [yearMsg, setYearMsg] = useState<string | null>(null);
  const items = plan.items ?? [];
  const last = graduationTerm(plan);
  const years = planYears(plan);
  const level = plan.entry_year_level ?? 1;
  const terms = planTerms(plan.entry_term, last);
  const shown = new Set(terms);
  const byTerm = new Map<string, PlanItem[]>();
  for (const item of items)
    byTerm.set(item.term, [...(byTerm.get(item.term) ?? []), item]);
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
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3">
          <PlanName name={name} onRename={onRename} />
          {verdict}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <GraduationField
            value={last}
            choices={choices}
            onChange={onGraduation}
          />
          <Button
            variant="outline"
            onClick={onToggleSummer}
            aria-pressed={showSummer}
          >
            {showSummer ? "Hide Summer" : "Show Summer"}
          </Button>
        </div>
      </div>
      {/* Issue #18: one column per academic year, each stacking its quarters (Summer, collapsed
          unless it is used, then Autumn, Winter and Spring). The columns follow the space the
          grid has (the planner panel takes a third of a wide screen), and a fifth year scrolls
          sideways. */}
      <div className="@container">
        <div
          data-testid="year-columns"
          className="grid grid-cols-1 gap-4 @lg:grid-cols-2 @3xl:auto-cols-[minmax(11rem,1fr)] @3xl:grid-flow-col @3xl:grid-cols-none @3xl:overflow-x-auto @3xl:pb-2"
        >
          {Array.from({ length: years }, (_, i) => i + 1).map((y) => {
            const start = academicYear(termAt(plan.entry_term, y, "AU"));
            const summer = termAt(plan.entry_term, y, "SU");
            const summerUsed =
              (byTerm.get(summer) ?? []).length > 0 || (proposals.get(summer) ?? []).length > 0;
            const summerShown = shown.has(summer) && (showSummer || summerUsed || openSummers.has(y));
            const yearTerms = QUARTERS.map((q) => termAt(plan.entry_term, y, q)).filter(
              (t) => shown.has(t) && !t.endsWith("-SU"),
            );
            return (
              <section
                key={y}
                aria-labelledby={`year-${y}`}
                data-testid={`year-${y}`}
                className="flex min-w-0 flex-col gap-3"
              >
                <h3
                  id={`year-${y}`}
                  className="flex flex-wrap items-baseline gap-x-2 font-display text-title-md"
                >
                  {classYearLabel(y, level)}{" "}
                  <span className="font-sans text-caption tabular-nums text-muted">
                    {academicYearLabel(start)}
                  </span>
                </h3>
                {summerShown ? (
                  <QuarterCell term={summer} items={byTerm.get(summer) ?? []} />
                ) : (
                  shown.has(summer) && (
                    <button
                      type="button"
                      onClick={() => setSummerOpen(y, true)}
                      className="flex min-h-11 items-center rounded-lg border border-dashed border-hairline px-3 text-caption text-muted transition-colors hover:border-hairline-strong hover:text-ink"
                    >
                      + {termLabel(summer)}
                    </button>
                  )
                )}
                {yearTerms.map((term) => (
                  <QuarterCell key={term} term={term} items={byTerm.get(term) ?? []} />
                ))}
              </section>
            );
          })}
        </div>
      </div>
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
          <Button
            variant="ghost"
            onClick={removeLastYear}
            disabled={years <= 1}
          >
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
