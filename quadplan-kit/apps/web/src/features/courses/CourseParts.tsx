import { Link } from "react-router-dom";
import type { AttributeValue, CourseDetail } from "@/api/types";
import { Badge } from "@/components/ui/misc";
import { isEstimate, round1 } from "@/features/planner/metrics";
import { quarterName, termLabel } from "@/features/planner/terms";

function CourseNode({ code, current = false }: { code: string; current?: boolean }) {
  const cls = "flex min-h-11 items-center justify-center rounded-md border px-3 text-sm font-medium";
  return current ? (
    <span className={`${cls} border-primary bg-primary text-primary-foreground`} aria-current="page">
      {code}
    </span>
  ) : (
    <Link to={`/courses/${encodeURIComponent(code)}`} className={`${cls} border-border bg-background hover:bg-muted`}>
      {code}
    </Link>
  );
}

/** What the course needs → the course → what it unlocks. */
export function PrereqGraph({ course }: { course: CourseDetail }) {
  return (
    <figure className="rounded-lg border border-border p-3" aria-labelledby="prereq-graph-caption">
      <figcaption id="prereq-graph-caption" className="mb-2 text-sm font-semibold">
        Prerequisite graph
      </figcaption>
      <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
        <div className="flex-1">
          <h3 className="mb-1 text-xs font-medium uppercase text-muted-foreground">Needs</h3>
          {course.needs.length ? (
            <ul className="flex flex-col gap-1">
              {course.needs.map((c) => (
                <li key={c}>
                  <CourseNode code={c} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Nothing</p>
          )}
        </div>
        <span aria-hidden="true" className="self-center text-xl text-muted-foreground">
          <span className="hidden sm:inline">→</span>
          <span className="sm:hidden">↓</span>
        </span>
        <div className="flex-1">
          <CourseNode code={course.code} current />
        </div>
        <span aria-hidden="true" className="self-center text-xl text-muted-foreground">
          <span className="hidden sm:inline">→</span>
          <span className="sm:hidden">↓</span>
        </span>
        <div className="flex-1">
          <h3 className="mb-1 text-xs font-medium uppercase text-muted-foreground">Unlocks</h3>
          {course.unlocks.length ? (
            <ul className="flex flex-col gap-1">
              {course.unlocks.map((c) => (
                <li key={c}>
                  <CourseNode code={c} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Nothing listed</p>
          )}
        </div>
      </div>
    </figure>
  );
}

function confidence(p: number): string {
  if (p >= 0.8) return "Likely";
  if (p >= 0.3) return "Possible";
  return "Unlikely";
}

export function OfferingsTable({ course }: { course: CourseDetail }) {
  const offerings = [...course.offerings].sort((a, b) => "AU WI SP SU".indexOf(a.quarter) - "AU WI SP SU".indexOf(b.quarter));
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="mb-1 text-left font-semibold">Predicted quarters</caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className="py-1 pr-2">Quarter</th>
              <th scope="col" className="py-1 pr-2">Chance offered</th>
              <th scope="col" className="py-1 pr-2">Basis</th>
            </tr>
          </thead>
          <tbody>
            {offerings.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-1 text-muted-foreground">No offering pattern recorded.</td>
              </tr>
            ) : (
              offerings.map((o) => (
                <tr key={o.quarter} className="border-b border-border">
                  <th scope="row" className="py-1 pr-2 font-normal">{quarterName(o.quarter)}</th>
                  <td className="py-1 pr-2">
                    {confidence(o.p_offered)} ({Math.round(o.p_offered * 100)}%)
                  </td>
                  <td className="py-1 pr-2">
                    {o.method === "catalog" ? "Catalog “Terms Offered”" : o.method}
                    {o.evidence_terms?.length ? ` (${o.evidence_terms.map(termLabel).join(", ")})` : ""}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="mb-1 text-left font-semibold">Offerings by term</caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className="py-1 pr-2">Term</th>
              <th scope="col" className="py-1 pr-2">Section</th>
              <th scope="col" className="py-1 pr-2">Instructor</th>
            </tr>
          </thead>
          <tbody>
            {course.sections.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-1 text-muted-foreground">No schedule data yet.</td>
              </tr>
            ) : (
              course.sections.map((s) => (
                <tr key={`${s.term}-${s.section_no}`} className="border-b border-border">
                  <th scope="row" className="py-1 pr-2 font-normal">{termLabel(s.term)}</th>
                  <td className="py-1 pr-2">
                    {s.section_no}
                    {s.component ? ` (${s.component})` : ""}
                  </td>
                  <td className="py-1 pr-2">
                    {(s.instructor_ids ?? [])
                      .map((id) => course.instructors.find((i) => i.instructor.slug === id)?.instructor.display_name ?? id)
                      .join(", ") || "TBA"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const ATTR_LABELS: Record<AttributeValue["key"], string> = {
  workload_hours: "Workload",
  difficulty: "Difficulty",
  intellectual_intensity: "Intellectual intensity",
  pace: "Pace",
  grading_strictness: "Grading strictness",
  recommend_rate: "Would recommend",
};

function attrValue(a: AttributeValue): string {
  if (a.key === "workload_hours") return `${round1(a.value)} h/week`;
  if (a.key === "recommend_rate") return `${Math.round(a.value * 100)}%`;
  return `${round1(a.value)} of 5`;
}

/** Workload, difficulty, intensity, pace; each with n, confidence and source. */
export function AttributeCard({ course }: { course: CourseDetail }) {
  const attrs = course.attributes.filter((a) => a.subject_type === "course");
  return (
    <section aria-labelledby="attr-heading" className="rounded-lg border border-border p-3">
      <h2 id="attr-heading" className="font-semibold">
        Course attributes
      </h2>
      {attrs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No attributes yet.</p>
      ) : (
        <dl className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {attrs.map((a) => (
            <div key={a.key} className="rounded-md bg-muted/50 p-2">
              <dt className="text-xs text-muted-foreground">{ATTR_LABELS[a.key]}</dt>
              <dd className="font-semibold">{attrValue(a)}</dd>
              <dd className="text-xs text-muted-foreground">
                {isEstimate(a) ? (
                  <Badge tone="amber">Estimate</Badge>
                ) : (
                  <Badge tone="blue">From {a.n} forum ratings</Badge>
                )}
                {a.ci_low != null && a.ci_high != null && ` · range ${round1(a.ci_low)}–${round1(a.ci_high)}`}
                {!isEstimate(a) && a.method === "blend" && " · blended with estimate"}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
