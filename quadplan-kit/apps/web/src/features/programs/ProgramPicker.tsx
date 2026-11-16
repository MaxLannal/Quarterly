import { useState } from "react";
import { usePrograms } from "@/api/hooks";
import { isNotAvailable } from "@/api/client";
import type { ProgramSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { ChoiceRow } from "@/components/ui/input";
import { Badge, ErrorText, NotAvailable, Spinner } from "@/components/ui/misc";

export const TYPE_LABELS: Record<ProgramSummary["type"], string> = {
  core: "Core curriculum",
  major: "Majors",
  minor: "Minors",
  bxms: "Bx/MS programs",
  joint: "Joint degrees",
  specialization: "Specializations",
  track: "Tracks",
  preprofessional: "Pre-professional paths",
  study_abroad_block: "Study-abroad blocks",
};

export function groupPrograms(programs: ProgramSummary[]): [ProgramSummary["type"], ProgramSummary[]][] {
  const order = Object.keys(TYPE_LABELS) as ProgramSummary["type"][];
  return order
    .map((t) => [t, programs.filter((p) => p.type === t).sort((a, b) => a.name.localeCompare(b.name))] as [ProgramSummary["type"], ProgramSummary[]])
    .filter(([, ps]) => ps.length > 0);
}

export function StatusBadge({ status }: { status: string }) {
  return status === "published" ? null : <Badge tone="warning" casing="normal">{status === "review" ? "Not yet hand-checked" : status}</Badge>;
}

/** Checkbox list of programs grouped by type; "in review" ones are labelled. */
export function ProgramChecklist({
  catalogYear,
  selected,
  onChange,
}: {
  catalogYear?: string;
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const q = usePrograms(catalogYear);
  if (q.isLoading) return <Spinner label="Loading programs" />;
  if (q.error) return isNotAvailable(q.error) ? <NotAvailable feature="The program list" /> : <ErrorText>Could not load programs.</ErrorText>;
  const groups = groupPrograms(q.data ?? []);
  if (groups.length === 0) return <p className="text-body-sm text-muted">No programs are loaded yet.</p>;
  return (
    <div className="space-y-5">
      {groups.map(([type, ps]) => (
        <fieldset key={type}>
          <legend className="mb-1 text-caption-uppercase uppercase text-muted">{TYPE_LABELS[type]}</legend>
          {ps.map((p) => (
            <ChoiceRow
              key={p.id}
              type="checkbox"
              checked={selected.includes(p.id)}
              onChange={(e) => onChange(e.target.checked ? [...selected, p.id] : selected.filter((x) => x !== p.id))}
            >
              {p.name} <StatusBadge status={p.status} />
            </ChoiceRow>
          ))}
        </fieldset>
      ))}
    </div>
  );
}

export function ProgramPickerBody({
  catalogYear,
  initial,
  onDone,
}: {
  catalogYear: string;
  initial: string[];
  onDone: (ids: string[]) => void;
}) {
  const [selected, setSelected] = useState(initial);
  return (
    <div className="space-y-5">
      <ProgramChecklist catalogYear={catalogYear} selected={selected} onChange={setSelected} />
      <Button className="w-full" onClick={() => onDone(selected)}>
        Save programs
      </Button>
    </div>
  );
}
