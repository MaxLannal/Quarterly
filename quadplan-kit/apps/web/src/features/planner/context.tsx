import { createContext, useContext } from "react";
import type { ChangeOp, CourseDetail, Issue, PlanItem, PlanState, ProgramSummary } from "@/api/types";
import type { EditResult } from "./planModel";
import { termLabel } from "./terms";

export interface RequirementTag {
  programId: string;
  label: string;
  /** Index into REQUIREMENT_COLORS (by program position on the plan). */
  color: number;
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

/** Left-border stripe colors for requirement tags (≥ 3:1 against white for the stripe). */
export const REQUIREMENT_COLORS = [
  "border-l-blue-700",
  "border-l-emerald-700",
  "border-l-purple-700",
  "border-l-orange-700",
  "border-l-pink-700",
  "border-l-teal-700",
];

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
