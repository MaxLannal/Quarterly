import { useId, useState, type FormEvent, type ReactNode } from "react";
import { api } from "@/api/client";
import type { Credit } from "@/api/types";
import { Button } from "@/components/ui/button";
import { CloseIcon, PencilIcon } from "@/components/ui/icons";
import { controlClass, controlCompactClass } from "@/components/ui/input";
import { CoursePicker } from "@/features/courses/CoursePicker";
import { cn } from "@/lib/utils";

const labelClass = "mb-1.5 block text-caption font-medium text-ink";
const KINDS: { value: Credit["kind"]; label: string }[] = [
  { value: "AP", label: "AP exam" },
  { value: "placement", label: "Placement" },
  // "Transfer", not "Transfer credit": the shorter word keeps a matched credit on one line in
  // the sign-up column (Richard, 2026-11-25).
  { value: "transfer", label: "Transfer" },
];

// D11 CR-1: the kind's own label, and plain words for an unmatched credit.
const kindLabel = (c: Credit) => KINDS.find((k) => k.value === c.kind)?.label ?? c.kind;
const creditName = (c: Credit) => `${c.label}${c.maps_to ? ` → ${c.maps_to}` : " (not matched to a course yet)"}`;

/** One line per credit: "AP exam: AP Calculus BC → MATH 15100 · 100 units". */
export function creditText(c: Credit): string {
  return `${kindLabel(c)}: ${creditName(c)} · ${c.units} units`;
}

/** The add and save buttons: as tall as the compact fields beside them (44px), so the row lines up. */
const rowButtonClass = "min-h-11 border-0 px-4";

/** Refuses a course code the catalog does not have: it would make every generated plan fail
 * its check (FEEDBACK "Generate Plan Failure"). */
async function codeProblem(
  code: string,
  catalogYear: string,
): Promise<string | null> {
  if (!code) return null;
  if (!/^[A-Z]{2,5} \d{5}$/.test(code))
    return "Course codes look like “ABCD 12345”.";
  const { response } = await api.GET("/courses/{code}", {
    params: { path: { code }, query: { catalog_year: catalogYear } },
  });
  return response.status === 404
    ? `${code} is not in the ${catalogYear} catalog. Leave this empty if you are not sure.`
    : null;
}

interface CreditFormProps {
  initial?: Credit;
  catalogYear: string;
  submitLabel: string;
  ariaLabel: string;
  onSubmit: (credit: Credit) => void;
  onCancel?: () => void;
  className?: string;
}

function CreditForm({
  initial,
  catalogYear,
  submitLabel,
  ariaLabel,
  onSubmit,
  onCancel,
  className,
}: CreditFormProps) {
  const id = useId();
  const [kind, setKind] = useState<Credit["kind"]>(initial?.kind ?? "AP");
  const [label, setLabel] = useState(initial?.label ?? "");
  const [mapsTo, setMapsTo] = useState(initial?.maps_to ?? "");
  const [units, setUnits] = useState(String(initial?.units ?? 100));
  const [pending, setPending] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const code = mapsTo.trim().toUpperCase();
    if (!label.trim())
      return setErr("Describe the credit, e.g. “AP Calculus BC, score 5”.");
    if (!code && pending)
      return setErr(
        "Choose the course from the list, or clear the field if you are not sure.",
      );
    const problem = await codeProblem(code, catalogYear);
    if (problem) return setErr(problem);
    setErr(null);
    onSubmit({
      kind,
      label: label.trim(),
      maps_to: code || null,
      units: Math.max(0, Math.round(Number(units)) || 0),
    });
    if (!initial) {
      setLabel("");
      setMapsTo("");
      setPending("");
    }
  }

  return (
    <form
      onSubmit={(e) => void submit(e)}
      className={cn("@container rounded-lg border border-hairline bg-canvas-soft p-3", className)}
      aria-label={ariaLabel}
    >
      {/* Richard (2026-11-25): a compact form. The fields keep the reading order Kind,
          Description, Course, Units in every width: Kind | Description, then Course | Units | Add
          in the sign-up column; one row in a wide panel; Course on its own row in a narrow
          drawer. No label wraps (D9). */}
      <div className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-3 @sm:grid-cols-[8.5rem_minmax(0,1fr)_6rem_auto] @2xl:grid-cols-[8.5rem_minmax(0,1fr)_minmax(0,1fr)_6rem_auto]">
        <div>
          <label htmlFor={`${id}-kind`} className={labelClass}>
            Kind
          </label>
          <select
            id={`${id}-kind`}
            className={cn(controlClass, controlCompactClass)}
            value={kind}
            onChange={(e) => setKind(e.target.value as Credit["kind"])}
          >
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </div>
        <div className="@sm:col-span-3 @2xl:col-span-1">
          <label htmlFor={`${id}-label`} className={labelClass}>
            Description
          </label>
          <input
            id={`${id}-label`}
            className={cn(controlClass, controlCompactClass)}
            value={label}
            placeholder="e.g. AP Calculus BC, 5"
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>
        <div className="col-span-2 @2xl:col-span-1">
          <label htmlFor={`${id}-maps`} className={cn(labelClass, "truncate")}>
            Counts as course <span className="font-normal text-muted">(if known)</span>
          </label>
          <CoursePicker
            id={`${id}-maps`}
            catalogYear={catalogYear}
            value={mapsTo}
            onChange={(code) => setMapsTo(code)}
            onPendingChange={setPending}
            compact
          />
        </div>
        <div>
          <label htmlFor={`${id}-units`} className={labelClass}>
            Units
          </label>
          <input
            id={`${id}-units`}
            type="number"
            min={0}
            className={cn(controlClass, controlCompactClass, "tabular-nums")}
            value={units}
            onChange={(e) => setUnits(e.target.value)}
          />
        </div>
        {onCancel ? null : (
          <div className="flex items-end">
            <Button type="submit" variant="outline" className={cn(rowButtonClass, "w-full")}>
              {submitLabel}
            </Button>
          </div>
        )}
        {err && (
          <p role="alert" className="col-span-full text-caption font-medium text-error">
            {err}
          </p>
        )}
        {onCancel && (
          <div className="col-span-full flex flex-wrap gap-2">
            <Button type="submit" variant="outline" className={rowButtonClass}>
              {submitLabel}
            </Button>
            <Button type="button" variant="ghost" className={rowButtonClass} onClick={onCancel}>
              Cancel
            </Button>
          </div>
        )}
      </div>
    </form>
  );
}

interface CreditsEditorProps {
  credits: Credit[];
  catalogYear: string;
  onChange: (credits: Credit[]) => void;
  intro?: ReactNode;
}

/**
 * Test, placement and transfer credits: see, edit, remove and add them (FEEDBACK "Viewing and
 * Editing Test, Placement and Transfer Credits", 2026-11-16). Used in onboarding and in the
 * planner's Credits panel.
 */
export function CreditsEditor({
  credits,
  catalogYear,
  onChange,
  intro,
}: CreditsEditorProps) {
  const [editing, setEditing] = useState<number | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  return (
    <div className="space-y-2">
      {intro && <p className="text-body-sm text-body">{intro}</p>}
      {credits.length === 0 ? (
        <p className="text-body-sm text-muted">No credits yet.</p>
      ) : (
        <ul className="@container space-y-1.5" aria-label="Your credits">
          {credits.map((c, i) =>
            editing === i ? (
              <li key={i}>
                <CreditForm
                  initial={c}
                  catalogYear={catalogYear}
                  submitLabel="Save credit"
                  ariaLabel={`Edit credit ${c.label}`}
                  onSubmit={(next) => {
                    onChange(credits.map((old, n) => (n === i ? next : old)));
                    setEditing(null);
                  }}
                  onCancel={() => setEditing(null)}
                />
              </li>
            ) : (
              <li
                key={i}
                className="flex min-h-11 items-center gap-1 rounded-lg border border-hairline bg-canvas-soft pl-3 text-body-sm text-ink"
              >
                {/* One line (Richard, 2026-11-25): the name is cut with "…" when it is too long,
                    the units always show, and the whole line is in the tooltip. `w-0` keeps the
                    long line from widening the page on a phone (it asks for no width of its own). */}
                <span className="flex w-0 min-w-0 flex-1 items-baseline overflow-hidden" title={creditText(c)}>
                  <span className="truncate">
                    {/* In a narrow list (a phone, the planner drawer) only screen readers get the
                        kind, so the name shows. */}
                    <span className="sr-only @sm:not-sr-only @sm:whitespace-pre">{`${kindLabel(c)}: `}</span>
                    {creditName(c)}
                  </span>
                  <span className="shrink-0 whitespace-pre tabular-nums">{` · ${c.units} units`}</span>
                </span>
                {confirming === i ? (
                  // D11 CR-2: confirm in place (DESIGN.md destructive pattern); removing can change the plan check.
                  <span className="flex shrink-0 items-center" role="group" aria-label={`Remove credit ${c.label}?`}>
                    <span className="px-1 text-caption text-muted">Remove?</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-error"
                      onClick={() => {
                        onChange(credits.filter((_, n) => n !== i));
                        setEditing(null);
                        setConfirming(null);
                      }}
                    >
                      Yes, remove
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                      Keep
                    </Button>
                  </span>
                ) : (
                  <span className="flex shrink-0">
                    <Button variant="ghost" size="sm" className="w-11 px-0" onClick={() => setEditing(i)} aria-label={`Edit credit ${c.label}`} title="Edit">
                      <PencilIcon />
                    </Button>
                    <Button variant="ghost" size="sm" className="w-11 px-0 text-error" onClick={() => setConfirming(i)} aria-label={`Remove credit ${c.label}`} title="Remove">
                      <CloseIcon />
                    </Button>
                  </span>
                )}
              </li>
            ),
          )}
        </ul>
      )}
      {/* D11 CR-3: a heading for the add form, hidden while another credit is being edited. */}
      {editing === null && (
        <>
          <h3 className="pt-1 text-body-sm font-medium text-ink">Add a credit</h3>
          <CreditForm catalogYear={catalogYear} submitLabel="Add credit" ariaLabel="Add a credit" onSubmit={(c) => onChange([...credits, c])} />
        </>
      )}
    </div>
  );
}
