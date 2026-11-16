import { useId, useState, type FormEvent, type ReactNode } from "react";
import { api } from "@/api/client";
import type { Credit } from "@/api/types";
import { Button } from "@/components/ui/button";
import { controlClass, controlCompactClass } from "@/components/ui/input";
import { CoursePicker } from "@/features/courses/CoursePicker";
import { cn } from "@/lib/utils";

const labelClass = "mb-1.5 block text-caption font-medium text-ink";
const KINDS: { value: Credit["kind"]; label: string }[] = [
  { value: "AP", label: "AP exam" },
  { value: "placement", label: "Placement" },
  { value: "transfer", label: "Transfer credit" },
];

/** One line per credit: "AP: AP Calculus BC → MATH 15100 · 100 units". */
export function creditText(c: Credit): string {
  return `${c.kind}: ${c.label}${c.maps_to ? ` → ${c.maps_to}` : " (needs mapping)"} · ${c.units} units`;
}

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
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_6rem] gap-3 rounded-lg border border-hairline bg-canvas-soft p-4",
        className,
      )}
      aria-label={ariaLabel}
    >
      {/* One column of full-width fields, Kind and Units sharing the first row: the form fits the
          planner's narrow drawer as well as onboarding, and no label wraps (D9, FEEDBACK
          "Minor design changes"). */}
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
      <div className="col-span-2">
        <label htmlFor={`${id}-label`} className={labelClass}>
          Description
        </label>
        <input
          id={`${id}-label`}
          className={cn(controlClass, controlCompactClass)}
          value={label}
          placeholder="e.g. AP Calculus BC, score 5"
          onChange={(e) => setLabel(e.target.value)}
        />
      </div>
      <div className="col-span-2">
        <label htmlFor={`${id}-maps`} className={labelClass}>
          Counts as course{" "}
          <span className="font-normal text-muted">(if known)</span>
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
      {err && (
        <p
          role="alert"
          className="col-span-2 text-caption font-medium text-error"
        >
          {err}
        </p>
      )}
      <div className="col-span-2 flex flex-wrap gap-2">
        <Button
          type="submit"
          variant="outline"
          className={onCancel ? undefined : "w-full"}
        >
          {submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
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
  return (
    <div className="space-y-3">
      {intro && <p className="text-body-sm text-body">{intro}</p>}
      {credits.length === 0 ? (
        <p className="text-body-sm text-muted">No credits yet.</p>
      ) : (
        <ul className="space-y-2" aria-label="Your credits">
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
                className="flex flex-wrap items-center justify-between gap-x-2 rounded-lg border border-hairline bg-canvas-soft py-1 pl-4 pr-1 text-body-sm text-ink"
              >
                <span className="min-w-0 py-2">{creditText(c)}</span>
                <span className="flex">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditing(i)}
                    aria-label={`Edit credit ${c.label}`}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      onChange(credits.filter((_, n) => n !== i));
                      setEditing(null);
                    }}
                    aria-label={`Remove credit ${c.label}`}
                  >
                    Remove
                  </Button>
                </span>
              </li>
            ),
          )}
        </ul>
      )}
      <CreditForm
        catalogYear={catalogYear}
        submitLabel="Add credit"
        ariaLabel="Add a credit"
        onSubmit={(c) => onChange([...credits, c])}
      />
    </div>
  );
}
