import { useState } from "react";
import { Link } from "react-router-dom";
import { usePrograms } from "@/api/hooks";
import type { PlanState } from "@/api/types";
import { inlineLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { ChoiceRow } from "@/components/ui/input";
import { Notice } from "@/components/ui/misc";
import { errorText, useProfile } from "@/features/dashboard/api";
import { studyAbroadProgramFor } from "./goals";
import { missingForPlan, planFromRecord } from "./setup";
import { graduationTerm, planYearCount, termLabel } from "./terms";

/**
 * "Set up a plan from your information" (Issue #16; it replaces the onboarding wizard): an empty
 * plan of a logged-in student is filled from the student record (first quarter and year,
 * expected graduation, intended programs plus the Core, credits, taken courses), and by default
 * the generator opens on it, as the wizard's last step did. A record without a first quarter or
 * programs links to the dashboard to answer them first.
 */
export function SetupCard({ catalogYear, onSetUp }: { catalogYear: string; onSetUp: (state: PlanState, generate: boolean) => void }) {
  const profile = useProfile(true);
  const programs = usePrograms(catalogYear);
  const [generate, setGenerate] = useState(true);

  if (profile.isLoading || programs.isLoading) return null;
  if (profile.error || !profile.data) {
    return (
      <Notice tone="info">
        Your information could not be loaded ({errorText(profile.error).toLowerCase()}). Add programs with “+ Program”, or open Requirements and drag courses onto the grid.
      </Notice>
    );
  }
  const record = profile.data;
  const catalog = programs.data ?? [];
  const coreIds = catalog.filter((p) => p.type === "core").map((p) => p.id);
  const missing = missingForPlan(record);
  const state = planFromRecord(record, catalogYear, coreIds, studyAbroadProgramFor(record.intended_programs, catalog));
  const names = new Map(catalog.map((p) => [p.id, p.name]));
  record.programs.forEach((p) => names.set(p.id, p.name));
  const last = graduationTerm(state);

  return (
    <section aria-labelledby="setup-title" className="rounded-xl border border-hairline bg-surface-card p-5 sm:p-6">
      <h2 id="setup-title" className="font-display text-title-md text-ink">
        Set up a plan from your information
      </h2>
      {missing.length > 0 ? (
        <p className="mt-2 text-body-sm text-body">
          First tell us {missing.includes("entry_term") ? "which quarter you started at UChicago" : ""}
          {missing.length === 2 ? " and " : ""}
          {missing.includes("intended_programs") ? "which majors or minors you intend to take" : ""}.{" "}
          <Link to="/me" className={inlineLinkClass}>
            Answer on your dashboard
          </Link>
          , then come back. Or add programs with “+ Program” and drag courses onto the grid.
        </p>
      ) : (
        <>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-body-sm text-body [&_dt]:text-caption-uppercase [&_dt]:uppercase [&_dt]:text-muted">
            <dt>Start</dt>
            <dd>
              {termLabel(state.entry_term)}
              {(state.entry_year_level ?? 1) > 1 ? `, entering year ${state.entry_year_level}` : ""}
            </dd>
            <dt>Years</dt>
            <dd>
              {planYearCount(state.entry_term, last)}, graduating in {termLabel(last)}
            </dd>
            <dt>Programs</dt>
            <dd>{(state.programs ?? []).map((p) => names.get(p.program_id) ?? p.program_id).join(", ")}</dd>
            <dt>Credits</dt>
            <dd>{state.credits?.length ? state.credits.map((c) => c.label).join(", ") : "None"}</dd>
            <dt>Taken courses</dt>
            <dd>{state.items?.length ? `${state.items.length} on the grid` : "None"}</dd>
          </dl>
          <div className="mt-3">
            <ChoiceRow type="checkbox" className="font-medium" checked={generate} onChange={(e) => setGenerate(e.target.checked)} aria-describedby="setup-generate-hint">
              Generate a starting plan
            </ChoiceRow>
            <p id="setup-generate-hint" className="pl-8 text-caption text-muted">
              Written by AI, then checked by the verifier. You choose what to keep.
            </p>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button onClick={() => onSetUp(state, generate)}>Set up my plan</Button>
            <Link to="/me" className={inlineLinkClass}>
              Change your information
            </Link>
          </div>
        </>
      )}
    </section>
  );
}
