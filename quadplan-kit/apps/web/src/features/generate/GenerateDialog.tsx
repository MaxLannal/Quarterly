import { useId, useRef, useState, type FormEvent } from "react";
import { isNotAvailable } from "@/api/client";
import { streamGenerate } from "@/api/sse";
import type { ChangeOp, GenerateRequest, Goal, PlanState, StepEvent, VariantEvent } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { CheckIcon, CloseIcon, ErrorIcon } from "@/components/ui/icons";
import { controlClass, controlCompactClass } from "@/components/ui/input";
import { NotAvailable, Notice } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { opsForTerms, termsTouched } from "@/features/planner/changes";
import { opText } from "@/features/planner/context";
import { goalLabel, round1 } from "@/features/planner/metrics";
import { planTerms, termLabel, compareTerms } from "@/features/planner/terms";
import { ReportBadge } from "@/features/planner/VerifierBadge";
import { applyStoredChangeSet, GENERATOR_MODE, generateDeterministic } from "./deterministic";

type Phase = "form" | "running" | "results";
type Scope = GenerateRequest["scope"];

const LOAD_LABELS: Record<string, string> = { "-1": "Much lighter", "-0.5": "Lighter", "0": "Balanced", "0.5": "Heavier", "1": "Much heavier" };

export interface GenerateFormValue {
  scope: Scope;
  selectedTerms: string[];
  load: number;
  perTermLoad: Record<string, number>;
  maxCourses: number | null;
  allowOverload: boolean;
  goals: Goal[];
  interests: string[];
  variants: number;
}

export function buildGenerateRequest(plan: PlanState, v: GenerateFormValue): GenerateRequest {
  return {
    plan,
    plan_id: null,
    scope: v.scope,
    selected_terms: v.scope === "selected" ? v.selectedTerms : [],
    load: v.load,
    per_term_load: v.perTermLoad,
    max_courses_per_term: v.maxCourses,
    allow_overload: v.allowOverload,
    goals: v.goals,
    interests: v.interests,
    variants: v.variants,
  };
}

function GenerateForm({ plan, years, onSubmit }: { plan: PlanState; years: number; onSubmit: (v: GenerateFormValue) => void }) {
  const terms = planTerms(plan.entry_term, years);
  const [scope, setScope] = useState<Scope>("whole");
  const [selectedTerms, setSelectedTerms] = useState<string[]>([]);
  const [load, setLoad] = useState(0);
  const [perTermLoad, setPerTermLoad] = useState<Record<string, number>>({});
  const [maxCourses, setMaxCourses] = useState<number | null>(null);
  const [allowOverload, setAllowOverload] = useState(false);
  const [goalIds, setGoalIds] = useState<Set<string>>(() => new Set((plan.goals ?? []).map((g) => g.id)));
  const [interests, setInterests] = useState<string[]>(() =>
    (plan.goals ?? []).flatMap((g) => (g.type === "interest" ? g.tags : [])),
  );
  const [tag, setTag] = useState("");
  const [variants, setVariants] = useState(2);
  const ids = { load: useId(), max: useId(), tag: useId(), variants: useId() };

  function addTag() {
    const t = tag.trim();
    if (t && !interests.includes(t)) setInterests([...interests, t]);
    setTag("");
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      scope,
      selectedTerms,
      load,
      perTermLoad,
      maxCourses,
      allowOverload,
      goals: (plan.goals ?? []).filter((g) => goalIds.has(g.id)),
      interests,
      variants,
    });
  }

  const box = cn(controlClass, controlCompactClass);
  return (
    <form onSubmit={submit} className="space-y-6 [&>fieldset+fieldset]:border-t [&>fieldset+fieldset]:border-hairline [&>fieldset+fieldset]:pt-5" aria-label="Generate plan options">
      <fieldset>
        <legend className="flex items-baseline gap-2 text-title-sm text-ink">1. Scope</legend>
        <p className="text-caption text-muted">Locked and completed courses are kept.</p>
        {(
          [
            ["whole", "Whole plan"],
            ["remaining", "Remaining quarters"],
            ["selected", "Selected quarters"],
          ] as const
        ).map(([value, label]) => (
          <label key={value} className="flex min-h-11 items-center gap-2 text-body-sm">
            <input type="radio" name="scope" value={value} checked={scope === value} onChange={() => setScope(value)} className="size-5" />
            {label}
          </label>
        ))}
        {scope === "selected" && (
          <div className="mt-1 grid grid-cols-2 gap-x-2 sm:grid-cols-4">
            {terms.map((t) => (
              <label key={t} className="flex min-h-11 items-center gap-2 text-caption">
                <input
                  type="checkbox"
                  className="size-5"
                  checked={selectedTerms.includes(t)}
                  onChange={(e) => setSelectedTerms(e.target.checked ? [...selectedTerms, t] : selectedTerms.filter((x) => x !== t))}
                />
                {termLabel(t)}
              </label>
            ))}
          </div>
        )}
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="flex items-baseline gap-2 text-title-sm text-ink">2. Load and difficulty</legend>
        <div>
          <label htmlFor={ids.load} className="block text-body-sm text-ink">
            Career-wide load: <strong>{LOAD_LABELS[String(load)]}</strong>
          </label>
          <div className="flex items-center gap-2 text-caption text-muted">
            <span aria-hidden="true">Lighter</span>
            <input
              id={ids.load}
              type="range"
              min={-1}
              max={1}
              step={0.5}
              value={load}
              aria-valuetext={LOAD_LABELS[String(load)]}
              onChange={(e) => setLoad(Number(e.target.value))}
              className="min-h-11 flex-1"
            />
            <span aria-hidden="true">Heavier</span>
          </div>
        </div>
        <details>
          <summary className="flex min-h-11 cursor-pointer items-center rounded-md text-body-sm font-medium text-ink">Per-quarter overrides</summary>
          <div className="grid gap-1 sm:grid-cols-2">
            {terms.map((t) => (
              <label key={t} className="flex items-center justify-between gap-2 text-caption">
                {termLabel(t)}
                <select
                  className={cn(box, "w-44")}
                  value={perTermLoad[t] ?? ""}
                  onChange={(e) => {
                    const next = { ...perTermLoad };
                    if (e.target.value === "") delete next[t];
                    else next[t] = Number(e.target.value);
                    setPerTermLoad(next);
                  }}
                >
                  <option value="">Same as career</option>
                  <option value="-1">Lighter</option>
                  <option value="1">Heavier</option>
                </select>
              </label>
            ))}
          </div>
        </details>
        <div>
          <label htmlFor={ids.max} className="mb-1.5 block text-body-sm text-ink">
            Maximum courses per quarter
          </label>
          <select id={ids.max} className={cn(box, "w-40")} value={maxCourses ?? ""} onChange={(e) => setMaxCourses(e.target.value ? Number(e.target.value) : null)}>
            <option value="">No limit</option>
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <label className="flex min-h-11 items-center gap-2 text-body-sm">
          <input type="checkbox" className="size-5" checked={allowOverload} onChange={(e) => setAllowOverload(e.target.checked)} />
          Allow a 500-unit quarter where the rules permit it
        </label>
      </fieldset>

      <fieldset>
        <legend className="flex items-baseline gap-2 text-title-sm text-ink">3. Goals</legend>
        {(plan.goals ?? []).length === 0 ? (
          <p className="text-body-sm text-muted">No goals yet. Add them in the Goals tab.</p>
        ) : (
          (plan.goals ?? []).map((g) => (
            <label key={g.id} className="flex min-h-11 items-center gap-2 text-body-sm">
              <input
                type="checkbox"
                className="size-5"
                checked={goalIds.has(g.id)}
                onChange={(e) => {
                  const next = new Set(goalIds);
                  if (e.target.checked) next.add(g.id);
                  else next.delete(g.id);
                  setGoalIds(next);
                }}
              />
              {goalLabel(g)}
              {g.term ? ` (${termLabel(g.term)})` : ""}
            </label>
          ))
        )}
      </fieldset>

      <fieldset>
        <legend className="flex items-baseline gap-2 text-title-sm text-ink">4. Interests</legend>
        <div className="mt-2 flex gap-2">
          <label htmlFor={ids.tag} className="sr-only">
            Interest tag
          </label>
          <input
            id={ids.tag}
            value={tag}
            placeholder="e.g. ML"
            onChange={(e) => setTag(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTag();
              }
            }}
            className={cn(box, "flex-1")}
          />
          <Button type="button" variant="outline" onClick={addTag}>
            Add
          </Button>
        </div>
        <ul className="mt-1 flex flex-wrap gap-x-1">
          {interests.map((t) => (
            <li key={t}>
              <Button type="button" variant="outline" size="sm" onClick={() => setInterests(interests.filter((x) => x !== t))} aria-label={`Remove interest ${t}`}>
                {t} <CloseIcon size={12} />
              </Button>
            </li>
          ))}
        </ul>
      </fieldset>

      <div className="border-t border-hairline pt-5">
        <label htmlFor={ids.variants} className="mb-2 block text-title-sm text-ink">
          5. Variants
        </label>
        <select id={ids.variants} className={cn(box, "w-28")} value={variants} onChange={(e) => setVariants(Number(e.target.value))}>
          {[1, 2, 3].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </div>

      <Button type="submit" className="w-full" disabled={scope === "selected" && selectedTerms.length === 0}>
        Generate
      </Button>
    </form>
  );
}

function VariantCard({ v, onApply, onDiscard }: { v: VariantEvent; onApply: (ops: ChangeOp[], terms: string[] | null) => void; onDiscard: () => void }) {
  const [showDiff, setShowDiff] = useState(false);
  const [picking, setPicking] = useState(false);
  const touched = termsTouched(v.change_set.ops).sort(compareTerms);
  const [picked, setPicked] = useState<string[]>(touched);
  const avg = v.metrics.avg_hours;
  const hardest = v.metrics.hardest_quarter_hours;
  const rationale = Object.entries(v.rationale).sort(([a], [b]) => compareTerms(a, b));
  return (
    <article className="space-y-3 rounded-xl border border-hairline bg-surface-card p-5" aria-label={`Variant ${v.label}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-title-sm">{v.label}</h3>
        <ReportBadge report={v.report} />
      </div>
      <p className="text-caption tabular-nums text-muted">
        {avg != null && `Average ${round1(avg)} h/wk`}
        {avg != null && hardest != null && " · "}
        {hardest != null && `Hardest quarter ${round1(hardest)} h/wk`}
      </p>
      {rationale.length > 0 && (
        <ul className="space-y-1 text-body-sm text-body [&_strong]:font-medium [&_strong]:text-ink">
          {rationale.map(([term, why]) => (
            <li key={term}>
              <strong>{termLabel(term)}:</strong> {why}
            </li>
          ))}
        </ul>
      )}
      {showDiff && (
        <div>
          <h4 className="text-caption-uppercase uppercase text-muted">Changes to your plan</h4>
          <ul className="mt-1 list-disc pl-5 text-body-sm marker:text-gray-dark">
            {v.change_set.ops.map((op, i) => (
              <li key={i}>{opText(op)}</li>
            ))}
          </ul>
        </div>
      )}
      {picking && (
        <fieldset>
          <legend className="text-caption-uppercase uppercase text-muted">Quarters to apply</legend>
          <div className="grid grid-cols-2 gap-x-2">
            {touched.map((t) => (
              <label key={t} className="flex min-h-11 items-center gap-2 text-body-sm">
                <input type="checkbox" className="size-5" checked={picked.includes(t)} onChange={(e) => setPicked(e.target.checked ? [...picked, t] : picked.filter((x) => x !== t))} />
                {termLabel(t)}
              </label>
            ))}
          </div>
          <Button className="mt-1" disabled={picked.length === 0} onClick={() => onApply(opsForTerms(v.change_set.ops, picked), picked)}>
            Apply {picked.length} quarter{picked.length === 1 ? "" : "s"}
          </Button>
        </fieldset>
      )}
      <div className="flex flex-wrap gap-2 border-t border-hairline pt-3">
        <Button onClick={() => onApply(v.change_set.ops, null)}>Apply</Button>
        <Button variant="outline" aria-expanded={showDiff} onClick={() => setShowDiff(!showDiff)}>
          {showDiff ? "Hide diff" : "View diff"}
        </Button>
        <Button variant="outline" aria-expanded={picking} onClick={() => setPicking(!picking)}>
          Apply selected quarters
        </Button>
        <Button variant="ghost" onClick={onDiscard}>
          Discard
        </Button>
      </div>
    </article>
  );
}

interface GenerateDialogProps {
  open: boolean;
  onClose: () => void;
  plan: PlanState;
  years: number;
  /** Returns true when the ops applied cleanly. */
  onApply: (ops: ChangeOp[]) => boolean;
  /** The saved plan's id when the plan is unchanged since it was saved; null otherwise. */
  planId?: string | null;
}

export function GenerateDialog({ open, onClose, plan, years, onApply, planId = null }: GenerateDialogProps) {
  const [phase, setPhase] = useState<Phase>("form");
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [variants, setVariants] = useState<VariantEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [infeasible, setInfeasible] = useState<{ message: string; conflicts?: { id: string; label: string }[] } | null>(null);
  const abort = useRef<AbortController | null>(null);

  function reset() {
    abort.current?.abort();
    setPhase("form");
    setSteps([]);
    setVariants([]);
    setError(null);
    setUnavailable(false);
    setInfeasible(null);
  }

  function close() {
    reset();
    onClose();
  }

  async function run(v: GenerateFormValue) {
    const controller = new AbortController();
    abort.current = controller;
    setPhase("running");
    setSteps([]);
    setVariants([]);
    setError(null);
    setInfeasible(null);
    try {
      if (GENERATOR_MODE === "deterministic") {
        setSteps([{ type: "step", name: "Loading requirements, solving and verifying", status: "started" }]);
        const result = await generateDeterministic(plan, v, controller.signal, planId);
        setSteps([{ type: "step", name: "Loading requirements, solving and verifying", status: "done" }]);
        setVariants(result.variants);
        setInfeasible(result.infeasible);
        setPhase("results");
        return;
      }
      for await (const ev of streamGenerate(buildGenerateRequest(plan, v), controller.signal)) {
        if (ev.type === "step") {
          setSteps((xs) => [...xs.filter((s) => s.name !== ev.name), ev]);
        } else if (ev.type === "variant") setVariants((xs) => [...xs, ev]);
        else if (ev.type === "error") setError(ev.message);
      }
      setPhase("results");
    } catch (e) {
      if (controller.signal.aborted) return;
      if (isNotAvailable(e)) setUnavailable(true);
      else setError("Plan generation failed. Try again.");
      setPhase("form");
    }
  }

  return (
    <Dialog open={open} onClose={close} title="Generate plan" description="A form, not a prompt: every choice maps to a typed setting." className="max-w-2xl">
      {unavailable && (
        <div className="mb-3">
          <NotAvailable feature="Plan generation">You can still build your plan by hand.</NotAvailable>
        </div>
      )}
      {error && (
        <Notice tone="error" role="alert" className="mb-3">
          {error}
        </Notice>
      )}
      {phase === "form" && <GenerateForm plan={plan} years={years} onSubmit={run} />}
      {phase === "running" && (
        <div role="status" aria-live="polite">
          <p className="mb-3 text-title-sm">Generating…</p>
          <ol className="space-y-2 text-body-sm text-body">
            {steps.map((s) => (
              <li key={s.name} className="flex items-center gap-2">
                {s.status === "done" ? (
                  <CheckIcon className="text-success" />
                ) : s.status === "failed" ? (
                  <ErrorIcon className="text-error" />
                ) : (
                  <span aria-hidden="true" className="inline-block size-2 animate-pulse rounded-pill bg-primary" />
                )}
                {s.name}
                <span className="sr-only"> ({s.status})</span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {phase === "results" && (
        <section aria-label="Generated variants" className="space-y-4">
          {infeasible && (
            <Notice tone="warning" role="status">
              <p className="font-medium">No plan fits all of these settings.</p>
              <p>{infeasible.message}</p>
            </Notice>
          )}
          {variants.length === 0 ? (
            !infeasible && <p className="text-body-sm">No variants were returned.</p>
          ) : (
            variants.map((v, i) => (
              <VariantCard
                key={`${v.label}-${i}`}
                v={v}
                onApply={async (ops, terms) => {
                  if (planId && v.change_set.id) {
                    try {
                      await applyStoredChangeSet(planId, v.change_set, terms);
                    } catch {
                      setError("Your plan changed since these options were made. Generate again.");
                      return;
                    }
                  }
                  if (onApply(ops)) close();
                }}
                onDiscard={() => setVariants((xs) => xs.filter((_, n) => n !== i))}
              />
            ))
          )}
          <Button variant="outline" onClick={reset}>
            Back to options
          </Button>
        </section>
      )}
    </Dialog>
  );
}
