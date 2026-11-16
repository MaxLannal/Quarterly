import { useState } from "react";
import { isWebUrl } from "@/lib/utils";
import { Link, useParams } from "react-router-dom";
import { ApiError, isNotAvailable } from "@/api/client";
import { useProgram } from "@/api/hooks";
import { inlineLinkClass, LoadingState, PageContainer, PageHeader, Section, standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge, NotAvailable, Notice } from "@/components/ui/misc";
import { activePlan, newLocalId, today, upsertPlan } from "@/features/planner/localPlans";
import { emptyPlan } from "@/features/planner/planModel";
import { compareTerms, termLabel } from "@/features/planner/terms";
import { StatusBadge, TYPE_LABELS } from "@/features/programs/ProgramPicker";
import { describe, ruleTree, type RuleEntry } from "@/features/programs/rules";

function RuleList({ entry }: { entry: RuleEntry }) {
  return (
    <li className="py-2">
      <span className="text-body-strong text-ink">{entry.label}</span>
      {entry.node?.needs_review || entry.part?.needs_review ? (
        <Badge tone="warning" className="ml-2 align-middle">
          Needs review
        </Badge>
      ) : null}
      <span className="block text-body-sm text-body">{describe(entry)}</span>
      {entry.children.length > 0 && (
        <ul className="ml-1 mt-1 border-l border-hairline-strong pl-5">
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
      <PageContainer as="section">
        <PageHeader title="Program" />
        <LoadingState label="Loading program" />
      </PageContainer>
    );
  }
  if (q.error || !q.data) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title={missing ? "Program not found" : "Program"} size="md" />
        <div className="flex flex-col gap-3">
          {isNotAvailable(q.error) ? <NotAvailable feature="Program pages" /> : <p className="text-body">{missing ? `No program ${id}.` : "Could not load this program."}</p>}
          <Link to="/programs" className={standaloneLinkClass}>
            All programs
          </Link>
        </div>
      </PageContainer>
    );
  }

  const p = q.data;
  const tree = ruleTree(p.id, p.rules);

  function addToPlan() {
    const plan = activePlan() ?? { localId: newLocalId(), name: "My Plan", isPrimary: true, state: emptyPlan(p.catalog_year), updatedDay: today() };
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
    <PageContainer as="article">
      <PageHeader
        title={p.name}
        eyebrow={TYPE_LABELS[p.type]}
        meta={
          <>
            {p.degree && <span>{p.degree}</span>}
            {p.department && <span>{p.department}</span>}
            <span>Catalog {p.catalog_year}</span>
            <StatusBadge status={p.status} />
          </>
        }
        description={<p>{p.verified_at ? `Checked against the catalog on ${p.verified_at.slice(0, 10)}.` : "Not yet verified by a curator."}</p>}
        actions={<Button onClick={addToPlan}>Add to my plan</Button>}
      >
        {added && (
          <Notice tone="success" role="status" className="max-w-reading">
            {added}{" "}
            <Link to="/plan" className="font-medium">
              Open the planner
            </Link>
          </Notice>
        )}
      </PageHeader>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:gap-8">
        <Section id="req" title="Requirements">
          <Card>
            <ul className="-my-2">
              <RuleList entry={{ ...tree, label: "All requirements" }} />
            </ul>
          </Card>
        </Section>

        <div className="flex flex-col gap-8">
          <Section id="sample" title="Sample path">
            {sample.length === 0 ? (
              <p className="text-body-sm text-muted">No sample path yet.</p>
            ) : (
              <ol className="divide-y divide-hairline border-y border-hairline">
                {sample.map((i, n) => (
                  <li key={n} className="flex items-baseline gap-3 py-3 text-body-sm">
                    <span className="w-6 shrink-0 text-caption tabular-nums text-muted">{n + 1}.</span>
                    <span className="text-ink">
                      {i.course ?? i.slot_ref} · <span className="text-body">{termLabel(i.term)}</span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </Section>

          <Section id="src" title="Sources">
            <ul className="flex flex-col gap-4">
              {p.sources.map((s, i) => (
                <li key={i} className="text-body-sm">
                  <blockquote className="border-l-2 border-hairline-strong pl-4 text-body">{s.quote}</blockquote>
                  {isWebUrl(s.url) && (
                    <a href={s.url} className={`${inlineLinkClass} mt-2 inline-flex min-h-11 items-center pl-4`} target="_blank" rel="noreferrer">
                      Catalog source ({p.catalog_year})
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </PageContainer>
  );
}
