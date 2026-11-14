import { Link } from "react-router-dom";
import type { AttributeValue, CourseDetail } from "@/api/types";
import { Card } from "@/components/ui/card";
import { ArrowIcon } from "@/components/ui/icons";
import { Badge } from "@/components/ui/misc";
import { isEstimate, round1 } from "@/features/planner/metrics";
import { quarterName, termLabel } from "@/features/planner/terms";

function CourseNode({ code, current = false }: { code: string; current?: boolean }) {
  const cls = "flex min-h-11 items-center justify-center rounded-pill border px-4 text-caption font-medium tabular-nums";
  return current ? (
    <span className={`${cls} border-primary bg-primary-wash text-ink`} aria-current="page">
      {code}
    </span>
  ) : (
    <Link to={`/courses/${encodeURIComponent(code)}`} className={`${cls} border-hairline-strong bg-surface-card text-ink transition-shadow hover:shadow-hover`}>
      {code}
    </Link>
  );
}

/** What the course needs → the course → what it unlocks. */
export function PrereqGraph({ course }: { course: CourseDetail }) {
  return (
    <figure className="rounded-xl border border-hairline bg-surface-card p-6" aria-labelledby="prereq-graph-caption">
      <figcaption id="prereq-graph-caption" className="mb-4 text-title-sm">
        Prerequisite graph
      </figcaption>
      <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
        <div className="flex-1">
          <h3 className="mb-2 text-caption-uppercase uppercase text-muted">Needs</h3>
          {course.needs.length ? (
            <ul className="flex flex-col gap-1">
              {course.needs.map((c) => (
                <li key={c}>
                  <CourseNode code={c} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-body-sm text-muted">Nothing</p>
          )}
        </div>
        <span aria-hidden="true" className="self-center text-gray-dark">
          <ArrowIcon size={20} className="rotate-90 sm:rotate-0" />
        </span>
        <div className="flex-1">
          <CourseNode code={course.code} current />
        </div>
        <span aria-hidden="true" className="self-center text-gray-dark">
          <ArrowIcon size={20} className="rotate-90 sm:rotate-0" />
        </span>
        <div className="flex-1">
          <h3 className="mb-2 text-caption-uppercase uppercase text-muted">Unlocks</h3>
          {course.unlocks.length ? (
            <ul className="flex flex-col gap-1">
              {course.unlocks.map((c) => (
                <li key={c}>
                  <CourseNode code={c} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-body-sm text-muted">Nothing listed</p>
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
    <div className="space-y-8">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-body-sm text-body">
          <caption className="mb-2 text-left text-title-sm text-ink">Predicted quarters</caption>
          <thead>
            <tr className="border-b border-hairline-strong">
              <th scope="col" className="py-2 pr-3 text-caption-uppercase uppercase text-muted">Quarter</th>
              <th scope="col" className="py-2 pr-3 text-caption-uppercase uppercase text-muted">Chance offered</th>
              <th scope="col" className="py-2 pr-3 text-caption-uppercase uppercase text-muted">Basis</th>
            </tr>
          </thead>
          <tbody>
            {offerings.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-2 text-muted">No offering pattern recorded.</td>
              </tr>
            ) : (
              offerings.map((o) => (
                <tr key={o.quarter} className="border-b border-hairline">
                  <th scope="row" className="py-2 pr-3 font-normal text-ink">{quarterName(o.quarter)}</th>
                  <td className="py-2 pr-3">
                    {confidence(o.p_offered)} ({Math.round(o.p_offered * 100)}%)
                  </td>
                  <td className="py-2 pr-3">
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
        <table className="w-full text-left text-body-sm text-body">
          <caption className="mb-2 text-left text-title-sm text-ink">Offerings by term</caption>
          <thead>
            <tr className="border-b border-hairline-strong">
              <th scope="col" className="py-2 pr-3 text-caption-uppercase uppercase text-muted">Term</th>
              <th scope="col" className="py-2 pr-3 text-caption-uppercase uppercase text-muted">Section</th>
              <th scope="col" className="py-2 pr-3 text-caption-uppercase uppercase text-muted">Instructor</th>
            </tr>
          </thead>
          <tbody>
            {course.sections.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-2 text-muted">No schedule data yet.</td>
              </tr>
            ) : (
              course.sections.map((s) => (
                <tr key={`${s.term}-${s.section_no}`} className="border-b border-hairline">
                  <th scope="row" className="py-2 pr-3 font-normal text-ink">{termLabel(s.term)}</th>
                  <td className="py-2 pr-3">
                    {s.section_no}
                    {s.component ? ` (${s.component})` : ""}
                  </td>
                  <td className="py-2 pr-3">
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
    <Card as="section" aria-labelledby="attr-heading" className="self-start">
      <h2 id="attr-heading" className="font-display text-display-sm">
        Course attributes
      </h2>
      {attrs.length === 0 ? (
        <p className="mt-4 text-body-sm text-muted">No attributes yet.</p>
      ) : (
        <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {attrs.map((a) => (
            <div key={a.key} className="rounded-lg bg-canvas-soft p-4">
              <dt className="text-caption text-muted">{ATTR_LABELS[a.key]}</dt>
              <dd className="mt-0.5 text-title-sm tabular-nums">{attrValue(a)}</dd>
              <dd className="mt-2 text-caption text-muted">
                {isEstimate(a) ? (
                  <Badge tone="warning" casing="normal">Estimate</Badge>
                ) : (
                  <Badge tone="info" casing="normal">From {a.n} forum ratings</Badge>
                )}
                {a.ci_low != null && a.ci_high != null && ` · range ${round1(a.ci_low)}–${round1(a.ci_high)}`}
                {!isEstimate(a) && a.method === "blend" && " · blended with estimate"}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  );
}
