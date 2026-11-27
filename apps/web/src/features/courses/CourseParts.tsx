import { Link } from "react-router-dom";
import type { AttributeValue, CourseDetail } from "@/api/types";
import { ArrowIcon } from "@/components/ui/icons";
import { Badge } from "@/components/ui/misc";
import { isEstimate, round1 } from "@/features/planner/metrics";
import { quarterName, termLabel } from "@/features/planner/terms";
import { cn } from "@/lib/utils";
import { Meter } from "./Glass";

function CourseNode({ code, current = false }: { code: string; current?: boolean }) {
  const cls = "flex min-h-11 items-center justify-center rounded-pill border px-4 font-mono text-[13px] font-medium uppercase tracking-[0.12em] tabular-nums";
  return current ? (
    <span
      className={`${cls} border-[rgb(255_120_140/0.55)] bg-[linear-gradient(180deg,rgb(255_92_112/0.3),rgb(160_16_44/0.25))] text-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.16),0_0_30px_-6px_rgb(255_60_90/0.6)]`}
      aria-current="page"
    >
      {code}
    </span>
  ) : (
    <Link
      to={`/courses/${encodeURIComponent(code)}`}
      className={`${cls} border-hairline-strong bg-white/[0.05] text-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.08)] transition-[border-color,box-shadow] duration-300 hover:border-primary/50 hover:shadow-[inset_0_1px_0_rgb(255_255_255/0.1),0_8px_24px_-10px_rgb(255_60_90/0.6)]`}
    >
      {code}
    </Link>
  );
}

/** What the course needs → the course → what it unlocks. */

/** What a predicted quarter rests on (`OfferingPattern.method`). */
const OFFERING_BASIS: Record<string, string> = {
  catalog: "Catalog “Terms Offered”",
  summer_session: "Summer Session course finder",
  history: "Past schedules",
};

const columnTitle = "mb-3 font-mono text-[10.5px] font-medium uppercase tracking-[0.2em] text-muted";

export function PrereqGraph({ course }: { course: CourseDetail }) {
  return (
    <figure className="rounded-[24px] border border-hairline bg-white/[0.03] p-6 shadow-[inset_0_1px_0_rgb(255_255_255/0.06)]" aria-labelledby="prereq-graph-caption">
      <figcaption id="prereq-graph-caption" className="mb-5 font-display text-display-sm text-ink">
        Prerequisite graph
      </figcaption>
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
        <div className="flex-1">
          <h3 className={columnTitle}>Needs</h3>
          {course.needs.length ? (
            <ul className="flex flex-col gap-2">
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
        <span aria-hidden="true" className="self-center text-primary drop-shadow-[0_0_6px_rgb(255_92_112/0.7)]">
          <ArrowIcon size={20} className="rotate-90 sm:rotate-0" />
        </span>
        <div className="flex-1">
          <CourseNode code={course.code} current />
        </div>
        <span aria-hidden="true" className="self-center text-primary drop-shadow-[0_0_6px_rgb(255_92_112/0.7)]">
          <ArrowIcon size={20} className="rotate-90 sm:rotate-0" />
        </span>
        <div className="flex-1">
          <h3 className={columnTitle}>Unlocks</h3>
          {course.unlocks.length ? (
            <ul className="flex flex-col gap-2">
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

const th = "py-3 pr-4 text-left font-mono text-[10.5px] font-medium uppercase tracking-[0.2em] text-muted";
const caption = "mb-3 text-left font-mono text-[11.5px] font-medium uppercase tracking-[0.2em] text-body-strong";

/**
 * The predicted quarters and the past sections, as two glass tables. Each quarter's chance is
 * written out and drawn as a thin lit meter beside it.
 */
export function OfferingsTable({ course }: { course: CourseDetail }) {
  const offerings = [...course.offerings].sort((a, b) => "AU WI SP SU".indexOf(a.quarter) - "AU WI SP SU".indexOf(b.quarter));
  const basisOf = (o: (typeof offerings)[number]) =>
    `${OFFERING_BASIS[o.method] ?? o.method}${o.evidence_terms?.length ? ` (${o.evidence_terms.map(termLabel).join(", ")})` : ""}`;
  // D11 CP-4: when every quarter has the same basis, say it once under the table.
  const oneBasis = offerings.length > 1 && offerings.every((o) => basisOf(o) === basisOf(offerings[0]!)) ? basisOf(offerings[0]!) : null;
  return (
    <div className="grid gap-10 xl:grid-cols-2 xl:gap-8">
      <div className="min-w-0 overflow-x-auto">
        <table className="w-full text-body-sm text-body">
          <caption className={caption}>Predicted quarters</caption>
          <thead>
            <tr className="border-b border-hairline-strong">
              <th scope="col" className={th}>Quarter</th>
              <th scope="col" className={th}>Chance offered</th>
              {!oneBasis && <th scope="col" className={th}>Basis</th>}
            </tr>
          </thead>
          <tbody>
            {offerings.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-3 text-muted">No offering pattern recorded.</td>
              </tr>
            ) : (
              offerings.map((o) => (
                <tr key={o.quarter} className="border-b border-hairline last:border-b-0">
                  <th scope="row" className="py-3.5 pr-4 text-left font-normal text-ink">{quarterName(o.quarter)}</th>
                  <td className="py-3.5 pr-4">
                    <span className="flex items-center gap-3">
                      <Meter share={o.p_offered} className="w-16 shrink-0 sm:w-24" />
                      <span className={cn(o.p_offered >= 0.8 ? "text-ink" : "text-body")}>
                        {o.p_offered === 0 ? "Not expected" : `${confidence(o.p_offered)} (${Math.round(o.p_offered * 100)}%)`}
                      </span>
                    </span>
                  </td>
                  {!oneBasis && <td className="py-3.5 pr-4">{basisOf(o)}</td>}
                </tr>
              ))
            )}
          </tbody>
        </table>
        {oneBasis && <p className="mt-3 text-caption text-muted">Basis: {oneBasis}</p>}
      </div>
      <div className="min-w-0 overflow-x-auto">
        <table className="w-full text-body-sm text-body">
          <caption className={caption}>Offerings by term</caption>
          <thead>
            <tr className="border-b border-hairline-strong">
              <th scope="col" className={th}>Term</th>
              <th scope="col" className={th}>Section</th>
              <th scope="col" className={th}>Instructor</th>
            </tr>
          </thead>
          <tbody>
            {course.sections.length === 0 ? (
              <tr>
                <td colSpan={3} className="py-3 text-muted">No schedule data yet.</td>
              </tr>
            ) : (
              course.sections.map((s) => (
                <tr key={`${s.term}-${s.section_no}`} className="border-b border-hairline last:border-b-0">
                  <th scope="row" className="py-3.5 pr-4 text-left font-normal text-ink">{termLabel(s.term)}</th>
                  <td className="py-3.5 pr-4 font-mono text-[13px] tracking-[0.06em]">
                    {s.section_no}
                    {s.component ? ` (${s.component})` : ""}
                  </td>
                  <td className="py-3.5 pr-4">
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
  if (a.key === "workload_hours") return `${round1(a.value)} h/wk`;
  if (a.key === "recommend_rate") return `${Math.round(a.value * 100)}%`;
  return `${round1(a.value)} / 5`;
}

/** The share of a full meter for an attribute (workload against 20 hours a week). */
function attrShare(a: AttributeValue): number {
  if (a.key === "workload_hours") return a.value / 20;
  if (a.key === "recommend_rate") return a.value;
  return a.value / 5;
}

/**
 * Workload, difficulty, intensity, pace; each with n, confidence and source. The page gives the
 * section its heading ("Course attributes"); each attribute is a glass tile with a lit meter.
 */
export function AttributeCard({ course }: { course: CourseDetail }) {
  const attrs = course.attributes.filter((a) => a.subject_type === "course");
  return (
    <div className="flex flex-col gap-5">
      {/* CP-1/CP-2 (D11): say what these numbers are, next to the overview's student ratings. */}
      <p className="max-w-reading text-body-sm text-muted">
        What the planner uses for this course, from all instructors. An estimate is not based on student ratings yet; the
        overview shows what students rated.
      </p>
      {attrs.length === 0 ? (
        <p className="text-body-sm text-muted">No attributes yet.</p>
      ) : (
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {attrs.map((a) => (
            <div key={a.key} className="qg-tile flex flex-col gap-2 p-5">
              <dt className="font-mono text-[10.5px] font-medium uppercase tracking-[0.18em] text-muted">{ATTR_LABELS[a.key]}</dt>
              <dd className="qg-numeral text-[40px]">{attrValue(a)}</dd>
              <dd aria-hidden="true">
                <Meter share={attrShare(a)} />
              </dd>
              <dd className="mt-1 text-caption text-muted">
                {isEstimate(a) ? (
                  <Badge tone="neutral" casing="normal">Estimate</Badge>
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
    </div>
  );
}
