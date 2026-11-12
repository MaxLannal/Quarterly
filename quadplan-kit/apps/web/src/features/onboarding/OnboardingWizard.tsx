import { DndContext, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useCatalogYears, usePrograms } from "@/api/hooks";
import type { Credit, Goal, PlanState } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/misc";
import { CAREER_PRESETS, interestGoal, TERM_PRESETS } from "@/features/planner/goals";
import { newLocalId, today, upsertPlan } from "@/features/planner/localPlans";
import { goalLabel } from "@/features/planner/metrics";
import { emptyPlan } from "@/features/planner/planModel";
import { catalogStartYear, catalogYearFor, termAt, termLabel } from "@/features/planner/terms";
import { ProgramChecklist } from "@/features/programs/ProgramPicker";
import { cn } from "@/lib/utils";

const STEPS = ["Entry term", "Credits", "Programs", "Goals", "Review"];
const box = "min-h-11 w-full rounded-md border border-border bg-background px-2 text-sm";

interface Draft {
  catalogYear: string;
  entryTerm: string;
  yearLevel: number;
  credits: Credit[];
  programs: string[];
  undecided: boolean;
  interests: string[];
  careerKeys: string[];
  termGoals: { key: string; term: string }[];
  generate: boolean;
}

// ------------------------------------------------------------------------------------------

function StepEntry({ d, set, years }: { d: Draft; set: (p: Partial<Draft>) => void; years: string[] }) {
  const id = useId();
  const start = catalogStartYear(d.catalogYear);
  const entryOptions = [`${start}-AU`, `${start + 1}-WI`, `${start + 1}-SP`];
  return (
    <div className="space-y-3">
      <div>
        <label htmlFor={`${id}-cy`} className="text-sm font-medium">
          Catalog year
        </label>
        <select id={`${id}-cy`} className={box} value={d.catalogYear} onChange={(e) => set({ catalogYear: e.target.value, entryTerm: `${catalogStartYear(e.target.value)}-AU` })}>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={`${id}-entry`} className="text-sm font-medium">
          First quarter at UChicago
        </label>
        <select id={`${id}-entry`} className={box} value={d.entryTerm} onChange={(e) => set({ entryTerm: e.target.value })}>
          {entryOptions.map((t) => (
            <option key={t} value={t}>
              {termLabel(t)}
            </option>
          ))}
        </select>
      </div>
      <fieldset>
        <legend className="text-sm font-medium">Status</legend>
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input type="radio" name="status" className="size-5" checked={d.yearLevel === 1} onChange={() => set({ yearLevel: 1 })} />
          First-year
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input type="radio" name="status" className="size-5" checked={d.yearLevel > 1} onChange={() => set({ yearLevel: 2 })} />
          Transfer student
        </label>
        {d.yearLevel > 1 && (
          <div>
            <label htmlFor={`${id}-level`} className="text-sm">
              Class standing at entry
            </label>
            <select id={`${id}-level`} className={box} value={d.yearLevel} onChange={(e) => set({ yearLevel: Number(e.target.value) })}>
              <option value={2}>Second year</option>
              <option value={3}>Third year</option>
            </select>
          </div>
        )}
      </fieldset>
    </div>
  );
}

function StepCredits({ d, set }: { d: Draft; set: (p: Partial<Draft>) => void }) {
  const id = useId();
  const [kind, setKind] = useState<Credit["kind"]>("AP");
  const [label, setLabel] = useState("");
  const [mapsTo, setMapsTo] = useState("");
  const [units, setUnits] = useState("100");
  const [err, setErr] = useState<string | null>(null);

  function add(e: FormEvent) {
    e.preventDefault();
    const code = mapsTo.trim().toUpperCase();
    if (!label.trim()) return setErr("Describe the credit, e.g. “AP Calculus BC, score 5”.");
    if (code && !/^[A-Z]{2,5} \d{5}$/.test(code)) return setErr("Course codes look like “ABCD 12345”.");
    setErr(null);
    set({ credits: [...d.credits, { kind, label: label.trim(), maps_to: code || null, units: Math.max(0, Math.round(Number(units)) || 0) }] });
    setLabel("");
    setMapsTo("");
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Optional. Credits with no known equivalent are flagged for manual mapping.</p>
      {d.credits.length > 0 && (
        <ul className="space-y-1">
          {d.credits.map((c, i) => (
            <li key={i} className="flex items-center justify-between gap-2 rounded-md border border-border p-2 text-sm">
              <span>
                {c.kind}: {c.label}
                {c.maps_to ? ` → ${c.maps_to}` : " (needs mapping)"} · {c.units} units
              </span>
              <Button variant="ghost" onClick={() => set({ credits: d.credits.filter((_, n) => n !== i) })} aria-label={`Remove credit ${c.label}`}>
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="grid gap-2 sm:grid-cols-2" aria-label="Add a credit">
        <div>
          <label htmlFor={`${id}-kind`} className="text-sm font-medium">
            Kind
          </label>
          <select id={`${id}-kind`} className={box} value={kind} onChange={(e) => setKind(e.target.value as Credit["kind"])}>
            <option value="AP">AP exam</option>
            <option value="placement">Placement</option>
            <option value="transfer">Transfer credit</option>
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-label`} className="text-sm font-medium">
            Description
          </label>
          <input id={`${id}-label`} className={box} value={label} onChange={(e) => setLabel(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`${id}-maps`} className="text-sm font-medium">
            Counts as course (if known)
          </label>
          <input id={`${id}-maps`} className={box} placeholder="ABCD 12345" value={mapsTo} onChange={(e) => setMapsTo(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`${id}-units`} className="text-sm font-medium">
            Units
          </label>
          <input id={`${id}-units`} type="number" min={0} className={box} value={units} onChange={(e) => setUnits(e.target.value)} />
        </div>
        {err && (
          <p role="alert" className="text-sm text-red-800 sm:col-span-2">
            {err}
          </p>
        )}
        <Button type="submit" variant="outline" className="sm:col-span-2">
          Add credit
        </Button>
      </form>
    </div>
  );
}

function StepPrograms({ d, set }: { d: Draft; set: (p: Partial<Draft>) => void }) {
  const id = useId();
  const [tag, setTag] = useState("");
  function addTag() {
    const t = tag.trim();
    if (t && !d.interests.includes(t)) set({ interests: [...d.interests, t] });
    setTag("");
  }
  return (
    <div className="space-y-3">
      <label className="flex min-h-11 items-center gap-2 text-sm font-medium">
        <input type="checkbox" className="size-5" checked={d.undecided} onChange={(e) => set({ undecided: e.target.checked })} />
        I&apos;m undecided
      </label>
      {!d.undecided && <ProgramChecklist catalogYear={d.catalogYear} selected={d.programs} onChange={(programs) => set({ programs })} />}
      <div>
        <label htmlFor={`${id}-tag`} className="text-sm font-medium">
          Interests {d.undecided ? "" : "(optional)"}
        </label>
        <div className="flex gap-2">
          <input
            id={`${id}-tag`}
            className={box}
            placeholder="e.g. philosophy of mind"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTag();
              }
            }}
          />
          <Button type="button" variant="outline" onClick={addTag}>
            Add
          </Button>
        </div>
        <ul className="mt-1 flex flex-wrap gap-1">
          {d.interests.map((t) => (
            <li key={t}>
              <Button variant="outline" className="px-2 text-xs" onClick={() => set({ interests: d.interests.filter((x) => x !== t) })} aria-label={`Remove interest ${t}`}>
                {t} <span aria-hidden="true">✕</span>
              </Button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ChipSource({ k, label, onPlace, terms, disabled }: { k: string; label: string; onPlace: (term: string) => void; terms: string[]; disabled: boolean }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: `chip:${k}`, data: { key: k }, disabled });
  const [term, setTerm] = useState(terms[0] ?? "");
  const id = useId();
  return (
    <li
      ref={setNodeRef}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined}
      className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-background p-1 text-sm"
    >
      <button
        type="button"
        aria-label={`Drag “${label}” onto a quarter`}
        className="flex min-h-11 min-w-11 cursor-grab touch-none items-center justify-center rounded-full border border-blue-700 px-3 text-blue-900"
        disabled={disabled}
        {...attributes}
        {...listeners}
      >
        {label}
      </button>
      <label htmlFor={id} className="sr-only">
        Quarter for {label}
      </label>
      <select id={id} className="min-h-11 rounded-md border border-border bg-background px-2 text-sm" value={term} onChange={(e) => setTerm(e.target.value)} disabled={disabled}>
        {terms.map((t) => (
          <option key={t} value={t}>
            {termLabel(t)}
          </option>
        ))}
      </select>
      <Button variant="outline" onClick={() => onPlace(term)} disabled={disabled}>
        Place
      </Button>
    </li>
  );
}

function TimelineCell({ term, chips, onRemove }: { term: string; chips: { key: string; i: number }[]; onRemove: (i: number) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: term });
  return (
    <div ref={setNodeRef} className={cn("min-h-16 rounded-md border border-border p-1 text-xs", isOver && "border-blue-700 bg-blue-50")} data-testid={`timeline-${term}`}>
      <div className="font-medium">{termLabel(term)}</div>
      <ul className="mt-1 flex flex-col gap-1">
        {chips.map((c) => (
          <li key={c.i}>
            <button
              type="button"
              onClick={() => onRemove(c.i)}
              aria-label={`Remove ${TERM_PRESETS.find((p) => p.key === c.key)?.label} from ${termLabel(term)}`}
              className="min-h-11 w-full rounded-full border border-blue-700 px-2 text-left text-blue-900 hover:bg-blue-50"
            >
              {TERM_PRESETS.find((p) => p.key === c.key)?.label} <span aria-hidden="true">✕</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StepGoals({ d, set, hasAbroad }: { d: Draft; set: (p: Partial<Draft>) => void; hasAbroad: boolean }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }), useSensor(KeyboardSensor));
  const terms: string[] = [];
  for (let y = 1; y <= 4; y += 1) for (const q of ["AU", "WI", "SP"] as const) terms.push(termAt(d.entryTerm, y, q));
  const place = (key: string, term: string) => set({ termGoals: [...d.termGoals, { key, term }] });
  function onDragEnd(e: DragEndEvent) {
    const key = (e.active.data.current as { key?: string } | undefined)?.key;
    if (key && e.over) place(key, String(e.over.id));
  }
  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="text-sm font-medium">Career-wide goals</legend>
        <div className="mt-1 flex flex-wrap gap-2">
          {CAREER_PRESETS.map((p) => {
            const on = d.careerKeys.includes(p.key);
            return (
              <button
                key={p.key}
                type="button"
                aria-pressed={on}
                onClick={() => set({ careerKeys: on ? d.careerKeys.filter((k) => k !== p.key) : [...d.careerKeys, p.key] })}
                className={cn("min-h-11 rounded-full border px-3 text-sm", on ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted")}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      </fieldset>
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <fieldset>
          <legend className="text-sm font-medium">Quarter goals: drag a chip onto a quarter, or pick one and press Place</legend>
          <ul className="mt-1 flex flex-col gap-1">
            {TERM_PRESETS.map((p) => (
              <ChipSource key={p.key} k={p.key} label={p.label} terms={terms} onPlace={(t) => place(p.key, t)} disabled={p.key === "study_abroad" && !hasAbroad} />
            ))}
          </ul>
        </fieldset>
        <div className="grid grid-cols-3 gap-1" aria-label="Timeline">
          {terms.map((t) => (
            <TimelineCell
              key={t}
              term={t}
              chips={d.termGoals.map((g, i) => ({ ...g, i })).filter((g) => g.term === t)}
              onRemove={(i) => set({ termGoals: d.termGoals.filter((_, n) => n !== i) })}
            />
          ))}
        </div>
      </DndContext>
    </div>
  );
}

function buildGoals(d: Draft, abroad: string | undefined): Goal[] {
  const goals: Goal[] = [];
  for (const key of d.careerKeys) goals.push(...(CAREER_PRESETS.find((p) => p.key === key)?.make(d.entryTerm) ?? []));
  for (const g of d.termGoals) {
    const goal = TERM_PRESETS.find((p) => p.key === g.key)?.make(g.term, { studyAbroadProgram: abroad });
    if (goal) goals.push(goal);
  }
  if (d.interests.length) goals.push(interestGoal(d.interests));
  return goals;
}

/** Undecided students keep only the Core (programs of type "core"). */
export function buildPlanState(d: Draft, abroad: string | undefined, coreIds: string[] = []): PlanState {
  return {
    ...emptyPlan(d.catalogYear, d.entryTerm),
    entry_year_level: d.yearLevel,
    credits: d.credits,
    programs: (d.undecided ? d.programs.filter((p) => coreIds.includes(p)) : d.programs).map((program_id) => ({ program_id, options: {}, version_id: null })),
    goals: buildGoals(d, abroad),
  };
}

export function OnboardingWizard() {
  const navigate = useNavigate();
  const yearsQ = useCatalogYears();
  const programsQ = usePrograms();
  const years = [...(yearsQ.data?.map((y) => y.id) ?? [])].sort().reverse();
  const fallback = catalogYearFor(new Date());
  const [step, setStep] = useState(0);
  const [d, setD] = useState<Draft>({
    catalogYear: fallback,
    entryTerm: `${catalogStartYear(fallback)}-AU`,
    yearLevel: 1,
    credits: [],
    programs: [],
    undecided: false,
    interests: [],
    careerKeys: [],
    termGoals: [],
    generate: true,
  });
  const [stored, setStored] = useState(true);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const set = (p: Partial<Draft>) => setD((x) => ({ ...x, ...p }));
  const abroad = (programsQ.data ?? []).find((p) => p.type === "study_abroad_block")?.id;
  const coreIds = (programsQ.data ?? []).filter((p) => p.type === "core").map((p) => p.id);

  // Default to the newest catalog year once the API lists them.
  const newest = years[0];
  useEffect(() => {
    if (newest) setD((x) => (x.catalogYear === fallback ? { ...x, catalogYear: newest, entryTerm: `${catalogStartYear(newest)}-AU` } : x));
  }, [newest, fallback]);

  // Move focus to the new step's heading (not on first load).
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [step]);

  function finish() {
    const state = buildPlanState(d, abroad, coreIds);
    const ok = upsertPlan({ localId: newLocalId(), name: "My plan", isPrimary: true, state, updatedDay: today() });
    if (!ok) {
      setStored(false);
      return;
    }
    navigate(d.generate ? "/plan?generate=1" : "/plan");
  }

  const yearChoices = years.length ? years : [d.catalogYear];
  const programNames = new Map((programsQ.data ?? []).map((p) => [p.id, p.name]));
  const goals = buildGoals(d, abroad);

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="text-2xl font-semibold">Planner setup</h1>
      <ol className="mt-3 flex flex-wrap gap-1 text-xs" aria-label="Steps">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={i === step ? "step" : undefined} className={cn("rounded-full border px-2 py-1", i === step ? "border-primary font-semibold text-primary" : "border-border text-muted-foreground")}>
            {i + 1}. {s}
          </li>
        ))}
      </ol>
      <section aria-labelledby="step-heading" className="mt-4 space-y-4 rounded-lg border border-border p-4">
        <h2 id="step-heading" ref={headingRef} tabIndex={-1} className="text-lg font-semibold">
          Step {step + 1} of 5: {STEPS[step]}
        </h2>
        {step === 0 && <StepEntry d={d} set={set} years={yearChoices} />}
        {step === 1 && <StepCredits d={d} set={set} />}
        {step === 2 && <StepPrograms d={d} set={set} />}
        {step === 3 && <StepGoals d={d} set={set} hasAbroad={!!abroad} />}
        {step === 4 && (
          <div className="space-y-3 text-sm">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
              <dt className="font-medium">Entry</dt>
              <dd>
                {termLabel(d.entryTerm)} ({d.yearLevel === 1 ? "first-year" : `transfer, year ${d.yearLevel}`}), catalog {d.catalogYear}
              </dd>
              <dt className="font-medium">Credits</dt>
              <dd>{d.credits.length ? d.credits.map((c) => c.label).join(", ") : "None"}</dd>
              <dt className="font-medium">Programs</dt>
              <dd>
                {[...(d.undecided ? d.programs.filter((p) => coreIds.includes(p)) : d.programs).map((p) => programNames.get(p) ?? p), ...(d.undecided ? ["Undecided"] : [])].join(", ") ||
                  "None"}
              </dd>
              <dt className="font-medium">Goals</dt>
              <dd>{goals.length ? goals.map((g) => `${goalLabel(g)}${g.term ? ` (${termLabel(g.term)})` : ""}`).join("; ") : "None"}</dd>
            </dl>
            <label className="flex min-h-11 items-center gap-2 font-medium">
              <input type="checkbox" className="size-5" checked={d.generate} onChange={(e) => set({ generate: e.target.checked })} />
              Generate a starting plan
            </label>
            {!stored && (
              <Notice tone="red" role="alert">
                This browser is blocking storage, so the plan cannot be kept. Allow site data or log in to save plans.
              </Notice>
            )}
          </div>
        )}
        <div className="flex flex-wrap justify-between gap-2 border-t border-border pt-3">
          <Button variant="outline" onClick={() => setStep(step - 1)} disabled={step === 0}>
            Back
          </Button>
          <div className="flex gap-2">
            {step === 1 && (
              <Button variant="ghost" onClick={() => setStep(2)}>
                Skip
              </Button>
            )}
            {step < 4 ? <Button onClick={() => setStep(step + 1)}>Next</Button> : <Button onClick={finish}>Create plan</Button>}
          </div>
        </div>
      </section>
    </div>
  );
}

