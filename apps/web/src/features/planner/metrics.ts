import type { AttributeValue, CourseDetail, CourseSummary, Goal, PlanItem } from "@/api/types";
import { termLabel } from "./terms";

type WithAttributes = Pick<CourseSummary, "attributes">;

/** A course-level attribute (pooled over instructors) when present, else any value for it. */
export function attribute(course: WithAttributes | undefined, key: AttributeValue["key"]): AttributeValue | undefined {
  const values = course?.attributes.filter((a) => a.key === key) ?? [];
  return values.find((a) => a.subject_type === "course") ?? values[0];
}

/** Forum-derived values count only with n >= 3; otherwise the value is an estimate (SPEC). */
export function isEstimate(a: AttributeValue): boolean {
  return a.method === "prior" || a.n < 3;
}

export function itemUnits(item: PlanItem, course: CourseDetail | undefined): number | null {
  return item.units ?? course?.units ?? null;
}

export interface QuarterMetrics {
  courses: number;
  units: number;
  /** True when some item's units are unknown (course details not loaded). */
  unitsPartial: boolean;
  hours: number;
  hoursPartial: boolean;
  difficulty: number;
  difficultyPartial: boolean;
}

/** Quarter footer: units, total hours/week and difficulty index (sum of difficulty, as V05/goals use). */
export function quarterMetrics(items: PlanItem[], courses: Map<string, CourseDetail>): QuarterMetrics {
  const m: QuarterMetrics = {
    courses: 0,
    units: 0,
    unitsPartial: false,
    hours: 0,
    hoursPartial: false,
    difficulty: 0,
    difficultyPartial: false,
  };
  for (const item of items) {
    const course = item.course ? courses.get(item.course) : undefined;
    m.courses += 1;
    const units = itemUnits(item, course);
    if (units == null) m.unitsPartial = true;
    else m.units += units;
    const hours = attribute(course, "workload_hours");
    if (hours) m.hours += hours.value;
    else m.hoursPartial = true;
    const diff = attribute(course, "difficulty");
    if (diff) m.difficulty += diff.value;
    else m.difficultyPartial = true;
  }
  return m;
}

export function round1(n: number): string {
  return (Math.round(n * 10) / 10).toString();
}

/** Short human label for a goal chip. */
export function goalLabel(goal: Goal): string {
  switch (goal.type) {
    case "course_load":
      if (goal.max_courses != null && goal.min_courses != null) return `${goal.min_courses}–${goal.max_courses} courses`;
      if (goal.max_courses != null) return `At most ${goal.max_courses} courses`;
      return `At least ${goal.min_courses ?? 0} courses`;
    case "workload_hours":
      return goal.aggregate === "career_average"
        ? `Average ≤ ${goal.max_hours} h/week`
        : `≤ ${goal.max_hours} h/week per quarter`;
    case "difficulty_cap":
      return goal.max_very_hard != null
        ? `At most ${goal.max_very_hard} very hard course${goal.max_very_hard === 1 ? "" : "s"}`
        : `Difficulty index ≤ ${goal.max_index}`;
    case "challenge":
      return `Challenge me (index ≥ ${goal.min_index})`;
    case "protect_gpa":
      return "Protect GPA";
    case "graduate_by":
      return `Graduate by ${termLabel(goal.by_term)}`;
    case "study_abroad":
      return `Study abroad: ${goal.program_id}, ${termLabel(goal.abroad_term)}`;
    case "bxms":
      return `Bx/MS application by ${termLabel(goal.apply_by)}`;
    case "premed":
      return `Pre-med courses by ${termLabel(goal.complete_by)}`;
    case "interest":
      return `Interests: ${goal.tags.join(", ")}`;
    case "light_quarter":
      return `Light quarter (≤ ${goal.max_courses} courses)`;
    case "language":
      return `${goal.language} ${goal.level} by ${termLabel(goal.by_term)}`;
  }
}
