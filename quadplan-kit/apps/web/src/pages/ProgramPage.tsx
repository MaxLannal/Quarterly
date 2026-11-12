import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, isNotAvailable } from "@/api/client";
import { useProgram } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Badge, NotAvailable, Notice, Spinner } from "@/components/ui/misc";
import { activePlan, newLocalId, today, upsertPlan } from "@/features/planner/localPlans";
import { emptyPlan } from "@/features/planner/planModel";
import { compareTerms, termLabel } from "@/features/planner/terms";
import { StatusBadge, TYPE_LABELS } from "@/features/programs/ProgramPicker";
import { describe, ruleTree, type RuleEntry } from "@/features/programs/rules";

function RuleList({ entry }: { entry: RuleEntry }) {
  return (
    <li className="py-1">
      <span className="font-medium">{entry.label}</span>
      {entry.node?.needs_review || entry.part?.needs_review ? (
        <Badge tone="amber" className="ml-2">
          Needs review
        </Badge>
      ) : null}
      <span className="block text-sm text-muted-foreground">{describe(entry)}</span>
      {entry.children.length > 0 && (
        <ul className="ml-4 border-l border-border pl-3">
          {entry.children.map((c) => (
            <RuleList key={c.path} entry={c} />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function ProgramPage() {
  const { id = "" } = useParams();
  const q = useProgram(id);
  const [added, setAdded] = useState<string | null>(null);

  if (q.isLoading) {
    return (
      <section className="mx-auto max-w-5xl p-4">
        <h1 className="text-2xl font-semibold">Program</h1>
        <Spinner label="Loading program" />
      </section>
    );
  }
  if (q.error || !q.data) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <section className="mx-auto max-w-5xl space-y-3 p-4">
        <h1 className="text-2xl font-semibold">{missing ? "Program not found" : "Program"}</h1>
        {isNotAvailable(q.error) ? <NotAvailable feature="Program pages" /> : <p>{missing ? `No program ${id}.` : "Could not load this program."}</p>}
        <Link to="/programs" className="text-primary underline">
          All programs
        </Link>
      </section>
    );
  }

  const p = q.data;
  const tree = ruleTree(p.id, p.rules);

  function addToPlan() {
    const plan = activePlan() ?? { localId: newLocalId(), name: "My plan", isPrimary: true, state: emptyPlan(p.catalog_year), updatedDay: today() };
    const programs = plan.state.programs ?? [];
    if (programs.some((x) => x.program_id === p.id)) {
      setAdded(`${p.name} is already on your plan.`);
      return;
    }
    const ok = upsertPlan({ ...plan, state: { ...plan.state, programs: [...programs, { program_id: p.id, options: {}, version_id: null }] } });
    setAdded(ok ? `Added ${p.name} to your plan.` : "Could not save: this browser is blocking storage.");
  }

  const sample = [...p.sample_path].sort((a, b) => compareTerms(a.term, b.term));
  return (
    <article className="mx-auto max-w-5xl space-y-5 p-4">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{p.name}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>{TYPE_LABELS[p.type]}</span>
          {p.degree && <span>{p.degree}</span>}
          {p.department && <span>{p.department}</span>}
          <span>Catalog {p.catalog_year}</span>
          <StatusBadge status={p.status} />
        </div>
        <p className="text-sm">
          {p.verified_at ? `Checked against the catalog on ${p.verified_at.slice(0, 10)}.` : "Not yet verified by a curator."}
        </p>
        <Button onClick={addToPlan}>Add to my plan</Button>
        {added && (
          <Notice tone="green" role="status">
            {added}{" "}
            <Link to="/plan" className="font-medium underline">
              Open the planner
            </Link>
          </Notice>
        )}
      </header>

      <section aria-labelledby="req-heading">
        <h2 id="req-heading" className="text-lg font-semibold">
          Requirements
        </h2>
        <ul>
          <RuleList entry={{ ...tree, label: "All requirements" }} />
        </ul>
      </section>

      <section aria-labelledby="sample-heading">
        <h2 id="sample-heading" className="text-lg font-semibold">
          Sample path
        </h2>
        {sample.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sample path yet.</p>
        ) : (
          <ol className="list-decimal pl-5">
            {sample.map((i, n) => (
              <li key={n}>
                {i.course ?? i.slot_ref} · {termLabel(i.term)}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section aria-labelledby="src-heading">
        <h2 id="src-heading" className="text-lg font-semibold">
          Sources
        </h2>
        <ul className="space-y-2">
          {p.sources.map((s, i) => (
            <li key={i} className="text-sm">
              <blockquote className="border-l-4 border-border pl-3 italic">{s.quote}</blockquote>
              {s.url && (
                <a href={s.url} className="text-primary underline" target="_blank" rel="noreferrer">
                  Catalog source ({p.catalog_year})
                </a>
              )}
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
