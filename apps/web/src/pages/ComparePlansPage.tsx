import { useId, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { PlanState } from "@/api/types";
import { EmptyState, PageContainer, PageHeader } from "@/components/layout/page";
import { Card } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/input";
import { loadPlans } from "@/features/planner/localPlans";
import { compareTerms, termLabel } from "@/features/planner/terms";
import "@/components/ui/folder.css";

interface Diff {
  onlyA: { course: string; term: string }[];
  onlyB: { course: string; term: string }[];
  moved: { course: string; a: string; b: string }[];
  same: number;
}

/** Course-level diff of two plans (the server's /plans/compare adds metrics later). */
export function diffPlans(a: PlanState, b: PlanState): Diff {
  const list = (p: PlanState) => (p.items ?? []).filter((i) => i.course).map((i) => ({ course: i.course as string, term: i.term }));
  const A = list(a);
  const B = list(b);
  const diff: Diff = { onlyA: [], onlyB: [], moved: [], same: 0 };
  const bLeft = [...B];
  for (const x of A) {
    const exact = bLeft.findIndex((y) => y.course === x.course && y.term === x.term);
    if (exact >= 0) {
      bLeft.splice(exact, 1);
      diff.same += 1;
      continue;
    }
    const moved = bLeft.findIndex((y) => y.course === x.course);
    if (moved >= 0) {
      diff.moved.push({ course: x.course, a: x.term, b: (bLeft[moved] as { term: string }).term });
      bLeft.splice(moved, 1);
    } else diff.onlyA.push(x);
  }
  diff.onlyB = bLeft;
  const byTerm = (x: { term: string }, y: { term: string }) => compareTerms(x.term, y.term);
  diff.onlyA.sort(byTerm);
  diff.onlyB.sort(byTerm);
  return diff;
}

export default function ComparePlansPage() {
  const plans = loadPlans().plans;
  const [a, setA] = useState(plans[0]?.localId ?? "");
  const [b, setB] = useState(plans[1]?.localId ?? "");
  const id = useId();
  const pa = plans.find((p) => p.localId === a);
  const pb = plans.find((p) => p.localId === b);
  const d = pa && pb ? diffPlans(pa.state, pb.state) : null;
  // Each side of the difference is a glass panel; its courses are small files.
  const column = (headingId: string, title: string, rows: ReactNode[], accent: string) => (
    <Card as="section" aria-labelledby={headingId} variant="compact" className="rounded-[24px] p-5 sm:p-6">
      <h2 id={headingId} className="mono-label flex items-center gap-2 text-muted">
        <span aria-hidden="true" className={`inline-block size-1.5 shrink-0 rounded-pill ${accent}`} />
        <span className="min-w-0 truncate">{title}</span>
      </h2>
      <p className="mt-2 font-display text-display-sm leading-none text-ink" aria-hidden="true">
        {rows.length}
      </p>
      {rows.length === 0 ? (
        <p className="mt-3 text-body-sm text-muted">None</p>
      ) : (
        <ul className="mt-4 flex flex-col gap-2 text-body-sm text-ink">{rows}</ul>
      )}
    </Card>
  );
  const row = "glass-file flex flex-wrap items-baseline gap-x-2 py-2 pl-3 pr-6";

  return (
    <PageContainer className="max-w-6xl">
      <PageHeader eyebrow="Plans // Side by side" title="Compare plans" />
      {plans.length < 2 ? (
        <EmptyState>
          You need two plans to compare.{" "}
          <Link to="/plans">
            Duplicate a plan
          </Link>{" "}
          first.
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-8">
          <Card variant="well" className="grid gap-4 rounded-[26px] sm:grid-cols-2 sm:p-6">
            <Field label="Plan A" htmlFor={`${id}-a`}>
              <Select id={`${id}-a`} value={a} onChange={(e) => setA(e.target.value)}>
                {plans.map((p) => (
                  <option key={p.localId} value={p.localId}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Plan B" htmlFor={`${id}-b`}>
              <Select id={`${id}-b`} value={b} onChange={(e) => setB(e.target.value)}>
                {plans.map((p) => (
                  <option key={p.localId} value={p.localId}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </Field>
          </Card>
          {d && d.onlyA.length + d.onlyB.length + d.moved.length === 0 && (
            // D11 MP-3: one sentence when there is nothing to compare.
            <p role="status" className="font-display text-title-md font-normal text-body">
              Same courses in the same quarters: {d.same} course{d.same === 1 ? "" : "s"} in both plans.
            </p>
          )}
          {d && d.onlyA.length + d.onlyB.length + d.moved.length > 0 && (
            <div className="grid gap-5 md:grid-cols-3">
              {column(
                "only-a",
                `Only in ${pa?.name ?? "the first plan"}`,
                d.onlyA.map((x, i) => (
                  <li key={i} className={row}>
                    <span className="font-mono text-[13px] font-semibold tracking-[0.04em]">{x.course}</span>
                    <span className="text-caption text-muted">· {termLabel(x.term)}</span>
                  </li>
                )),
                "bg-primary shadow-[0_0_8px_var(--color-primary)]",
              )}
              {column(
                "only-b",
                `Only in ${pb?.name ?? "the second plan"}`,
                d.onlyB.map((x, i) => (
                  <li key={i} className={row}>
                    <span className="font-mono text-[13px] font-semibold tracking-[0.04em]">{x.course}</span>
                    <span className="text-caption text-muted">· {termLabel(x.term)}</span>
                  </li>
                )),
                "bg-data-1 shadow-[0_0_8px_var(--color-data-1)]",
              )}
              {column(
                "moved",
                "Different quarter",
                d.moved.map((x, i) => (
                  <li key={i} className={row}>
                    <span className="font-mono text-[13px] font-semibold tracking-[0.04em]">{x.course}:</span>
                    <span className="text-caption text-muted">
                      {termLabel(x.a)} → {termLabel(x.b)}
                    </span>
                  </li>
                )),
                "bg-warning shadow-[0_0_8px_var(--color-warning)]",
              )}
              <p className="mono-label text-muted md:col-span-3">
                {d.same} course{d.same === 1 ? " is" : "s are"} the same in both.
              </p>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
