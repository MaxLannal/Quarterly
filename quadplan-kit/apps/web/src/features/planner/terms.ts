/**
 * Term arithmetic, ported from `packages/planner_core/planner_core/terms.py`.
 * Term ids are `<calendar year>-<quarter>`: Autumn 2026 is `2026-AU`, the following Winter is
 * `2027-WI`. An academic year runs AU, WI, SP, SU.
 */
import type { Quarter } from "@/api/types";

/** Display order inside one academic year. */
export const QUARTERS: readonly Quarter[] = ["AU", "WI", "SP", "SU"];
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

/** The calendar year in which the term's academic year starts (2027-WI -> 2026). */
export function academicYear(term: string): number {
  const [year, quarter] = parseTerm(term);
  return quarter === "AU" ? year : year - 1;
}

/** 1-based plan year of `term` for a student who entered in `entryTerm`. */
export function yearIndex(term: string, entryTerm: string): number {
  return academicYear(term) - academicYear(entryTerm) + 1;
}

/** The term id of `quarter` in plan year `year` (1-based). */
export function termAt(entryTerm: string, year: number, quarter: Quarter): string {
  const start = academicYear(entryTerm) + year - 1;
  return `${quarter === "AU" ? start : start + 1}-${quarter}`;
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

/** All terms of plan years 1..years, in grid order. */
export function planTerms(entryTerm: string, years: number): string[] {
  const out: string[] = [];
  for (let y = 1; y <= years; y += 1) for (const q of QUARTERS) out.push(termAt(entryTerm, y, q));
  return out;
}
