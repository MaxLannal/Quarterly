import { useId, useState } from "react";
import { Link } from "react-router-dom";
import type { PlanState } from "@/api/types";
import { loadPlans } from "@/features/planner/localPlans";
import { compareTerms, termLabel } from "@/features/planner/terms";

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
  const box = "min-h-11 w-full rounded-md border border-border bg-background px-2";

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4">
      <h1 className="text-2xl font-semibold">Compare plans</h1>
      {plans.length < 2 ? (
        <p>
          You need two plans to compare.{" "}
          <Link to="/plans" className="text-primary underline">
            Duplicate a plan
          </Link>{" "}
          first.
        </p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor={`${id}-a`} className="text-sm font-medium">
                Plan A
              </label>
              <select id={`${id}-a`} className={box} value={a} onChange={(e) => setA(e.target.value)}>
                {plans.map((p) => (
                  <option key={p.localId} value={p.localId}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor={`${id}-b`} className="text-sm font-medium">
                Plan B
              </label>
              <select id={`${id}-b`} className={box} value={b} onChange={(e) => setB(e.target.value)}>
                {plans.map((p) => (
                  <option key={p.localId} value={p.localId}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {d && (
            <div className="grid gap-4 sm:grid-cols-3">
              <section aria-labelledby="only-a">
                <h2 id="only-a" className="font-semibold">
                  Only in A
                </h2>
                <ul className="text-sm">{d.onlyA.map((x, i) => <li key={i}>{x.course} · {termLabel(x.term)}</li>)}</ul>
              </section>
              <section aria-labelledby="only-b">
                <h2 id="only-b" className="font-semibold">
                  Only in B
                </h2>
                <ul className="text-sm">{d.onlyB.map((x, i) => <li key={i}>{x.course} · {termLabel(x.term)}</li>)}</ul>
              </section>
              <section aria-labelledby="moved">
                <h2 id="moved" className="font-semibold">
                  Different quarter
                </h2>
                <ul className="text-sm">
                  {d.moved.map((x, i) => (
                    <li key={i}>
                      {x.course}: {termLabel(x.a)} → {termLabel(x.b)}
                    </li>
                  ))}
                </ul>
              </section>
              <p className="text-sm text-muted-foreground sm:col-span-3">{d.same} courses are the same in both.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
