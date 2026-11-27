import { useState, type ReactNode } from "react";
import { cn, isWebUrl } from "@/lib/utils";
import { Link, useParams } from "react-router-dom";
import { ApiError, isNotAvailable } from "@/api/client";
import { useProgram } from "@/api/hooks";
import { inlineLinkClass, LoadingState, PageContainer, PageHeader, standaloneLinkClass, tallTargetClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { GlassFile, GlassFolder } from "@/components/ui/folder";
import { Badge, NotAvailable, Notice } from "@/components/ui/misc";
import { FactChip, FactChips, Kicker } from "@/features/courses/Glass";
import { activePlan, newLocalId, today, upsertPlan } from "@/features/planner/localPlans";
import { emptyPlan } from "@/features/planner/planModel";
import { compareTerms, termLabel } from "@/features/planner/terms";
import { StatusBadge, TYPE_LABELS } from "@/features/programs/ProgramPicker";
import { describe, ruleTree, type RuleEntry } from "@/features/programs/rules";

/** One program's type, in the singular (D11 PR-4; TYPE_LABELS are group headings). */
const TYPE_SINGULAR: Record<keyof typeof TYPE_LABELS, string> = {
  core: "Core curriculum",
  major: "Major",
  minor: "Minor",
  bxms: "Bx/MS program",
  joint: "Joint degree",
  specialization: "Specialization",
  track: "Track",
  preprofessional: "Pre-professional path",
  study_abroad_block: "Study-abroad block",
};

/** "2099-07-01..." as "July 1, 2099" (D11 PR-4); the day only, as stored. */
function humanDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso.slice(0, 10);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
}

const COURSE_CODE = /\b[A-Z]{2,5} \d{5}\b/g;

/** Text with every course code linked to its course page (D11 PR-1: the explorer is not a dead end). */
function LinkedCodes({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(COURSE_CODE)) {
    const at = m.index ?? 0;
    if (at > last) parts.push(text.slice(last, at));
    parts.push(
      <Link key={at} to={`/courses/${encodeURIComponent(m[0])}`} className={cn(inlineLinkClass, "tabular-nums")}>
        {m[0]}
      </Link>,
    );
    last = at + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}

const unchecked = (entry: RuleEntry) => !!(entry.node?.needs_review || entry.part?.needs_review);

function RuleList({ entry }: { entry: RuleEntry }) {
  return (
    <li className="py-2">
      <span className="text-body-strong text-ink">{entry.label}</span>
      {unchecked(entry) ? (
        <Badge tone="warning" casing="normal" className="ml-2 align-middle">
          Not yet hand-checked
        </Badge>
      ) : null}
      <span className="block text-body-sm text-body">
        <LinkedCodes text={describe(entry)} />
      </span>
      {entry.children.length > 0 && (
        <ul className="qg-thread ml-1 mt-1 pl-5">
          {entry.children.map((c) => (
            <RuleList key={c.path} entry={c} />
          ))}
        </ul>
      )}
    </li>
  );
}

/**
 * The requirements as a glass folder: the whole program is the folder, each requirement group a
 * file standing in it (its own sub-rules nested on the file with a luminous guide line).
 */
function Requirements({ tree }: { tree: RuleEntry }) {
  if (tree.children.length === 0) {
    return (
      <div className="qg-tile p-6">
        <ul className="-my-2">
          <RuleList entry={{ ...tree, label: "All requirements" }} />
        </ul>
      </div>
    );
  }
  return (
    <GlassFolder
      tone="ember"
      tabRatio={0.42}
      tab={<span className="text-body-strong text-ink">All requirements <span className="font-normal text-on-night-soft">· {describe(tree).toLowerCase()}</span></span>}
    >
      <ul className="grid gap-3 sm:grid-cols-2">
        {tree.children.map((c, i) => (
          <li key={c.path} className="min-w-0">
            <GlassFile className="flex h-full flex-col gap-2 p-5 pr-7 [&_a]:text-ink [&_a]:decoration-primary [&_a:hover]:text-primary-hover">
              <span className="font-mono text-[10.5px] font-medium uppercase tracking-[0.18em] text-on-night-soft">Part {String(i + 1).padStart(2, "0")}</span>
              <span className="text-body-strong text-ink">
                {c.label}
                {unchecked(c) ? (
                  <Badge tone="warning" casing="normal" className="ml-2 align-middle">
                    Not yet hand-checked
                  </Badge>
                ) : null}
              </span>
              <span className="block text-body-sm text-body">
                <LinkedCodes text={describe(c)} />
              </span>
              {c.children.length > 0 && (
                <ul className="qg-thread mt-1 pl-4">
                  {c.children.map((g) => (
                    <RuleList key={g.path} entry={g} />
                  ))}
                </ul>
              )}
            </GlassFile>
          </li>
        ))}
      </ul>
    </GlassFolder>
  );
}

/** A side panel: a mono kicker over a serif heading. */
function Panel({ id, kicker, title, children }: { id: string; kicker: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="qg-tile flex min-w-0 flex-col gap-4 p-6 sm:p-7">
      <div className="flex flex-col gap-2">
        <Kicker>{kicker}</Kicker>
        <h2 id={`${id}-heading`} className="font-display text-display-sm text-ink">
          {title}
        </h2>
      </div>
      {children}
    </section>
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
      {/* The course page's cover language: kicker, display serif, two-line glass fact chips. */}
      <header className="qg-hero flex flex-col pb-12 pt-4 sm:pt-12">
        <Kicker className="mb-5">
          <Link to="/programs" className={cn("hover:text-ink", tallTargetClass)}>
            Programs
          </Link>{" "}
          <span aria-hidden="true" className="text-muted-soft">//</span> {TYPE_SINGULAR[p.type]}
        </Kicker>
        <h1 className="max-w-[20ch] font-display text-display-lg text-ink [text-shadow:0_0_60px_rgb(255_92_112/0.22)] sm:text-display-mega">{p.name}</h1>
        <p className="mt-5 max-w-reading text-[19px] leading-[1.55] text-body">
          {p.verified_at ? `Checked against the catalog on ${humanDate(p.verified_at)}.` : "Not yet verified by a curator."}
        </p>
        <FactChips label="Program facts" className="mt-8">
          <FactChip label="Type">{TYPE_SINGULAR[p.type]}</FactChip>
          {p.degree && <FactChip label="Degree">{p.degree}</FactChip>}
          {p.department && <FactChip label="Department">{p.department}</FactChip>}
          <FactChip label="Catalog">{p.catalog_year}</FactChip>
          <FactChip label="Status">{p.status === "published" ? "Published" : <StatusBadge status={p.status} />}</FactChip>
        </FactChips>
        <div className="mt-8 flex flex-col items-start gap-3">
          <Button onClick={addToPlan}>Add to plan</Button>
          {added && (
            <Notice tone="success" role="status" className="max-w-reading">
              {added}{" "}
              <Link to="/plan" className="font-medium">
                Open the planner
              </Link>
            </Notice>
          )}
        </div>
      </header>

      <div className="grid gap-12 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)] lg:gap-10">
        <section id="req" aria-labelledby="req-heading" className="min-w-0 scroll-mt-24">
          <div className="mb-6 flex flex-col gap-2 border-b border-hairline pb-4">
            <Kicker>01 <span aria-hidden="true" className="text-muted-soft">//</span> What it takes</Kicker>
            <h2 id="req-heading" className="font-display text-display-sm text-ink sm:text-display-md">
              Requirements
            </h2>
          </div>
          <Requirements tree={tree} />
        </section>

        <div className="flex min-w-0 flex-col gap-4 lg:pt-[92px]">
          <Panel id="sample" kicker="02 // One way through" title="Sample path">
            {sample.length === 0 ? (
              <p className="text-body-sm text-muted">No sample path yet.</p>
            ) : (
              <ol className="qg-thread flex flex-col pl-5">
                {sample.map((i, n) => (
                  <li key={n} className="relative flex items-baseline gap-3 py-2.5 text-body-sm">
                    <span aria-hidden="true" className="absolute -left-[23px] top-[17px] size-[7px] rounded-pill bg-primary shadow-[0_0_8px_rgb(255_92_112/0.8)]" />
                    <span className="w-6 shrink-0 font-mono text-[11.5px] tabular-nums text-muted">{n + 1}.</span>
                    <span className="text-ink">
                      {i.course ? <LinkedCodes text={i.course} /> : i.slot_ref} · <span className="text-body">{termLabel(i.term)}</span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </Panel>

          <Panel id="src" kicker="03 // In the catalog's words" title="Sources">
            <ul className="flex flex-col gap-4">
              {p.sources.map((s, i) => (
                <li key={i} className="text-body-sm">
                  <blockquote className="border-l border-primary/60 pl-4 font-serif text-[17px] italic leading-[1.55] text-body">{s.quote}</blockquote>
                  {isWebUrl(s.url) && (
                    <a href={s.url} className={`${inlineLinkClass} mt-2 inline-flex min-h-11 items-center pl-4`} target="_blank" rel="noreferrer">
                      Catalog source ({p.catalog_year})
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </PageContainer>
  );
}
