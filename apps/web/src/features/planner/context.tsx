import { createContext, useContext } from "react";
import type { ChangeOp, CourseDetail, Issue, PlanItem, PlanState, ProgramSummary } from "@/api/types";
import type { EditResult } from "./planModel";
import { termLabel } from "./terms";

export interface RequirementTag {
  programId: string;
  label: string;
  /** What kind of requirement the course fills: sets the card's colour strip. */
  kind: StripKind;
}

export interface PlannerContextValue {
  plan: PlanState;
  courses: Map<string, CourseDetail>;
  programs: ProgramSummary[];
  issues: Issue[];
  /** Item ids and terms highlighted by the selected issue. */
  highlight: { items: Set<string>; terms: Set<string> };
  tags: Map<string, RequirementTag>;
  edit: (result: EditResult) => void;
  applyOps: (ops: ChangeOp[]) => void;
  openMoveTo: (item: PlanItem) => void;
  openAddTo: (course: string) => void;
}

export const PlannerContext = createContext<PlannerContextValue | null>(null);

export function usePlanner(): PlannerContextValue {
  const ctx = useContext(PlannerContext);
  if (!ctx) throw new Error("usePlanner outside <PlannerContext>");
  return ctx;
}

/** Left-border stripe colors for requirement tags: DESIGN.md data-1 … data-6, in order. The
 *  stripe is never the only signal; the card also names the requirement in text. */
/**
 * The colour strip on a course card (and on each program in the requirement tree) says what
 * kind of requirement the course fills; the same kind always has the same colour, on every
 * plan (FEEDBACK "Color strip", 2026-11-16). The card's text already names the program and
 * the requirement, so the colour only has to agree with words the student can read; no legend.
 *
 * - major: maroon, the site's own colour, for the student's (first) major, its tracks and
 *   specializations. The main thing a plan is for gets the strongest colour.
 * - second_major: blue (data-1), the next most important.
 * - core: yellow (data-2): the College's shared general education, warm and distinct.
 * - minor: light green (data-3).
 * - abroad: orange (data-4), a study-abroad block, away from campus.
 * - graduate: mauve (data-5), Bx/MS and joint degrees (graduate-level work).
 * - preprofessional: dark green (data-6).
 * - none: grey hairline, a course that counts toward no requirement (a free elective).
 */
export type StripKind = "major" | "second_major" | "core" | "minor" | "abroad" | "graduate" | "preprofessional" | "none";

export const STRIP_CLASSES: Record<StripKind, string> = {
  major: "border-l-primary",
  second_major: "border-l-data-1",
  core: "border-l-data-2",
  minor: "border-l-data-3",
  abroad: "border-l-data-4",
  graduate: "border-l-data-5",
  preprofessional: "border-l-data-6",
  none: "border-l-hairline-strong",
};

/** The kind of a program on this plan; `planPrograms` in the plan's order (first major wins). */
export function stripKind(programId: string, planPrograms: string[], types: Map<string, ProgramSummary["type"]>): StripKind {
  switch (types.get(programId)) {
    case "core":
      return "core";
    case "major": {
      const majors = planPrograms.filter((id) => types.get(id) === "major");
      return majors.indexOf(programId) > 0 ? "second_major" : "major";
    }
    case "specialization":
    case "track":
      return "major";
    case "minor":
      return "minor";
    case "study_abroad_block":
      return "abroad";
    case "bxms":
    case "joint":
      return "graduate";
    case "preprofessional":
      return "preprofessional";
    default:
      return "none";
  }
}

/** Issues that point at an item: same course, and same term when the issue names terms. */
export function issuesForItem(issues: Issue[], item: PlanItem): Issue[] {
  return issues.filter(
    (i) =>
      !!item.course &&
      (i.course_ids ?? []).includes(item.course) &&
      ((i.term_ids ?? []).length === 0 || (i.term_ids ?? []).includes(item.term)),
  );
}

/** Items and terms an issue highlights on the grid. */
export function highlightFor(issue: Issue | null, items: PlanItem[]): { items: Set<string>; terms: Set<string> } {
  const out = { items: new Set<string>(), terms: new Set<string>() };
  if (!issue) return out;
  const courseIds = issue.course_ids ?? [];
  const termIds = issue.term_ids ?? [];
  for (const item of items) {
    const courseHit = courseIds.length > 0 && !!item.course && courseIds.includes(item.course);
    const termHit = termIds.length === 0 || termIds.includes(item.term);
    if (courseHit && termHit && item.id) out.items.add(item.id);
  }
  if (courseIds.length === 0) termIds.forEach((t) => out.terms.add(t));
  return out;
}

/** Plain-English description of a change op, for diffs and proposal cards. */
export function opText(op: ChangeOp): string {
  const target = (o: { course?: string | null; slot_ref?: string | null; item_id?: string | null }) =>
    o.course ?? o.slot_ref ?? o.item_id ?? "item";
  switch (op.op) {
    case "add":
      return `Add ${op.course ?? op.slot_ref} to ${termLabel(op.term)}${op.locked ? " (locked)" : ""}`;
    case "move":
      return `Move ${target(op)}${op.from_term ? ` from ${termLabel(op.from_term)}` : ""} to ${termLabel(op.to_term)}`;
    case "remove":
      return `Remove ${target(op)}${op.term ? ` from ${termLabel(op.term)}` : ""}`;
    case "lock":
      return `Lock ${target(op)}`;
    case "unlock":
      return `Unlock ${target(op)}`;
  }
}
