/**
 * Term arithmetic, ported from `packages/planner_core/planner_core/terms.py`.
 * Term ids are `<calendar year>-<quarter>`: Autumn 2026 is `2026-AU`, the following Winter is
 * `2027-WI`. An academic year runs SU, AU, WI, SP: the summer *before* autumn belongs to it
 * (Summer 2026 is in 2026-27), so a transfer student can start with that summer and nothing
 * follows a graduating student's last spring (FEEDBACK F2).
 */
import type { Quarter } from "@/api/types";

/** Display order inside one academic year. */
export const QUARTERS: readonly Quarter[] = ["SU", "AU", "WI", "SP"];
/** Quarters that open an academic year in their own calendar year. */
const STARTS_YEAR: readonly Quarter[] = ["SU", "AU"];
const CALENDAR_ORDER: Record<Quarter, number> = { WI: 0, SP: 1, SU: 2, AU: 3 };
const QUARTER_NAMES: Record<Quarter, string> = {
  AU: "Autumn",
  WI: "Winter",
  SP: "Spring",
  SU: "Summer",
};

function isQuarter(q: string): q is Quarter {
  return q in CALENDAR_ORDER;
}

export function parseTerm(term: string): [number, Quarter] {
  const [year, quarter] = term.split("-");
  if (!year || !quarter || !isQuarter(quarter) || !/^\d{4}$/.test(year)) {
    throw new Error(`not a term id: ${JSON.stringify(term)}`);
  }
  return [Number(year), quarter];
}

/** Sort key: chronological order. */
export function termKey(term: string): number {
  const [year, quarter] = parseTerm(term);
  return year * 4 + CALENDAR_ORDER[quarter];
}

export function compareTerms(a: string, b: string): number {
  return termKey(a) - termKey(b);
}

export function isBefore(a: string, b: string): boolean {
  return termKey(a) < termKey(b);
}

/** The calendar year in which the term's academic year starts (2027-WI -> 2026, 2026-SU -> 2026). */
export function academicYear(term: string): number {
  const [year, quarter] = parseTerm(term);
  return STARTS_YEAR.includes(quarter) ? year : year - 1;
}

/** 1-based plan year of `term` for a student who entered in `entryTerm`. */
export function yearIndex(term: string, entryTerm: string): number {
  return academicYear(term) - academicYear(entryTerm) + 1;
}

/** The term id of `quarter` in plan year `year` (1-based). */
export function termAt(entryTerm: string, year: number, quarter: Quarter): string {
  const start = academicYear(entryTerm) + year - 1;
  return `${STARTS_YEAR.includes(quarter) ? start : start + 1}-${quarter}`;
}

/** `Y2-SP` -> absolute term id for this entry term; absolute ids pass through. */
export function resolveTermRef(ref: string, entryTerm: string): string {
  if (ref.startsWith("Y")) {
    const [year, quarter] = ref.slice(1).split("-");
    if (!quarter || !isQuarter(quarter)) throw new Error(`not a term reference: ${JSON.stringify(ref)}`);
    return termAt(entryTerm, Number(year), quarter);
  }
  parseTerm(ref);
  return ref;
}

export function quarterOf(term: string): Quarter {
  return parseTerm(term)[1];
}

export function quarterName(q: Quarter): string {
  return QUARTER_NAMES[q];
}

/** "Autumn 2026". */
export function termLabel(term: string): string {
  try {
    const [year, quarter] = parseTerm(term);
    return `${QUARTER_NAMES[quarter]} ${year}`;
  } catch {
    return term;
  }
}

/** The first catalog-year start year for an id like `2026-27`. */
export function catalogStartYear(catalogYear: string): number {
  return Number(catalogYear.slice(0, 4));
}

/** The academic year (as a catalog-year id) a date falls in: Nov 2026 -> "2026-27". */
export function catalogYearFor(date: Date): string {
  const start = date.getMonth() >= 6 ? date.getFullYear() : date.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

/** The newest catalog year the API lists, or the current academic year if it lists none. */
export function defaultCatalogYear(ids: string[] | undefined): string {
  const sorted = [...(ids ?? [])].sort().reverse();
  return sorted[0] ?? catalogYearFor(new Date());
}

/** "2026–27" for the academic year that starts in 2026. */
export function academicYearLabel(start: number): string {
  return `${start}–${String((start + 1) % 100).padStart(2, "0")}`;
}

/**
 * The default last quarter: the Spring of the last year, counting the years left from the class
 * standing at entry (four for a first-year, three for a second-year transfer). Same rule as
 * `planner_core.generator.graduation_term`.
 */
export function defaultGraduationTerm(entryTerm: string, entryYearLevel: number = 1): string {
  return termAt(entryTerm, Math.max(1, 5 - entryYearLevel), "SP");
}

/** The plan's last quarter: its `graduation_term`, else the default. */
export function graduationTerm(plan: { entry_term: string; entry_year_level?: number; graduation_term?: string | null }): string {
  return plan.graduation_term ?? defaultGraduationTerm(plan.entry_term, plan.entry_year_level ?? 1);
}

/**
 * The longest plan: the graduation quarter at most 6 academic years after entry, so 7 plan
 * years. Same limit as `planner_core.models.PlanState` (the API refuses longer plans).
 */
export const MAX_PLAN_YEARS = 7;

/** Number of plan years shown: up to and including the graduation quarter's year. */
export function planYearCount(entryTerm: string, lastTerm: string): number {
  return Math.max(1, yearIndex(lastTerm, entryTerm));
}

/** All terms of the plan, in grid order (Summer first in each year), ending at `lastTerm`. */
export function planTerms(entryTerm: string, lastTerm: string): string[] {
  const out: string[] = [];
  const years = planYearCount(entryTerm, lastTerm);
  for (let y = 1; y <= years; y += 1) {
    for (const q of QUARTERS) {
      const t = termAt(entryTerm, y, q);
      if (!isBefore(lastTerm, t)) out.push(t);
    }
  }
  return out;
}

const ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"];

/** Class year of plan year `year` for a student who entered at `entryYearLevel`: "Second year". */
export function classYearLabel(year: number, entryYearLevel: number = 1): string {
  const n = year + entryYearLevel - 1;
  const word = ORDINALS[n - 1];
  return word ? `${word} year` : `Year ${n}`;
}
