import { useId, useState, type ReactNode } from "react";
import type { Credit } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { controlClass, controlCompactClass, FieldHint } from "@/components/ui/input";
import { CreditsEditor } from "@/features/credits/CreditsEditor";
import { CoursePicker } from "@/features/courses/CoursePicker";
import { ChipField } from "@/features/dashboard/parts";
import { termLabel } from "@/features/planner/terms";
import { ProgramChecklist } from "@/features/programs/ProgramPicker";
import { cn } from "@/lib/utils";
import { columnLabel, termChoices, type Question, type QuestionSet, type RecordCredit, type TakenCourse, type TakenCourseOut, type TermAway } from "./questions";

const labelClass = "mb-1.5 block text-caption font-medium text-ink";
const compact = cn(controlClass, controlCompactClass);

export interface AnswerControlProps {
  question: Question;
  set: QuestionSet | undefined;
  /** The field's current value (the record's shape: `null` = not answered). */
  value: unknown;
  onChange: (value: unknown) => void;
  classYear: number | null | undefined;
  catalogYear: string;
  /** Program names for the panel layout's chips (the record's `programs`). */
  programNames?: Map<string, string>;
  /** `form`: the registration form (labels are the question text, programs listed inline);
   * `panel`: a dashboard panel (labels are the short label, programs in a dialog). */
  layout?: "form" | "panel";
}

/**
 * The control that fits a question's type: a select for one choice or a quarter, chips for
 * several, a 1-10 row for a scale, a list editor, the credits editor, or a small table. Every
 * label, option and help line comes from the question file.
 */
export function AnswerControl(props: AnswerControlProps) {
  const { question, layout = "form" } = props;
  const id = useId();
  const label = layout === "form" ? question.text : question.label;
  const hint = layout === "form" && question.help ? question.help : null;
  const field = question.field;

  if (field === "credits") return <CreditsField {...props} label={label} hint={hint} />;
  if (field === "taken_courses") return <TakenCoursesField {...props} label={label} hint={hint} />;
  if (field === "terms_away") return <TermsAwayField {...props} label={label} hint={hint} />;
  if (question.value === "program") return <ProgramsField {...props} label={label} hint={hint} />;
  if (question.type === "list") {
    return (
      <Group label={label} hint={hint} as="div">
        <ChipField label={question.label} items={(props.value as string[] | null) ?? []} onChange={(items) => props.onChange(items)} />
      </Group>
    );
  }
  if (question.type === "multi") return <MultiField {...props} label={label} hint={hint} />;
  if (question.type === "scale") return <ScaleField {...props} label={label} hint={hint} />;
  return (
    <div className="flex min-w-0 flex-col">
      <label htmlFor={id} className={labelClass}>
        {label}
      </label>
      <SingleSelect id={id} {...props} describedBy={hint ? `${id}-hint` : undefined} />
      {hint && <FieldHint id={`${id}-hint`}>{hint}</FieldHint>}
    </div>
  );
}

/** A labelled group of controls (a fieldset, or a div for a single compound control). */
function Group({ label, hint, children, as = "fieldset" }: { label: string; hint?: string | null; children: ReactNode; as?: "fieldset" | "div" }) {
  const id = useId();
  if (as === "div") {
    return (
      <div role="group" aria-labelledby={id} className="flex min-w-0 flex-col gap-2">
        <p id={id} className="text-caption font-medium text-ink">
          {label}
        </p>
        {hint && <FieldHint>{hint}</FieldHint>}
        {children}
      </div>
    );
  }
  return (
    <fieldset className="flex min-w-0 flex-col gap-2">
      <legend className="mb-1.5 text-caption font-medium text-ink">{label}</legend>
      {hint && <FieldHint>{hint}</FieldHint>}
      {children}
    </fieldset>
  );
}

/** One choice from the options, or a quarter for a term question. */
function SingleSelect({ id, question, value, onChange, classYear, describedBy }: AnswerControlProps & { id: string; describedBy?: string }) {
  if (question.value === "term") {
    const terms = termChoices(question.field, classYear, value as string | null);
    return (
      <select id={id} aria-describedby={describedBy} className={compact} value={(value as string | null) ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">Not answered</option>
        {terms.map((t) => (
          <option key={t} value={t}>
            {termLabel(t)}
          </option>
        ))}
      </select>
    );
  }
  const index = question.options.findIndex((o) => o.value === value);
  return (
    <select
      id={id}
      aria-describedby={describedBy}
      className={compact}
      value={index >= 0 ? String(index) : ""}
      onChange={(e) => onChange(e.target.value === "" ? null : (question.options[Number(e.target.value)]?.value ?? null))}
    >
      <option value="">Not answered</option>
      {question.options.map((o, i) => (
        <option key={String(o.value)} value={String(i)}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

/** Several options as toggle chips; each press saves the new list (none chosen = "none"). */
function MultiField({ question, value, onChange, label, hint }: AnswerControlProps & { label: string; hint: string | null }) {
  const chosen = (value as unknown[] | null) ?? [];
  return (
    <Group label={label} hint={hint}>
      <div className="flex flex-wrap gap-2">
        {question.options.map((o) => {
          const on = chosen.includes(o.value);
          return (
            <button
              key={String(o.value)}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(on ? chosen.filter((v) => v !== o.value) : question.options.map((x) => x.value).filter((v) => v === o.value || chosen.includes(v)))}
              className={cn("min-h-11 cursor-pointer rounded-pill border px-4 text-body-sm transition-colors", on ? "border-primary bg-primary-wash text-ink" : "border-hairline-strong bg-surface-card text-ink hover:bg-surface-strong")}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </Group>
  );
}

/** A scale as a row of numbered buttons, its two ends named under it. */
function ScaleField({ question, value, onChange, label, hint }: AnswerControlProps & { label: string; hint: string | null }) {
  const min = question.min ?? 1;
  const max = question.max ?? 10;
  const steps = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  return (
    <Group label={label} hint={hint}>
      <div className="flex flex-wrap gap-1">
        {steps.map((n) => (
          <button
            key={n}
            type="button"
            aria-pressed={value === n}
            aria-label={`${n}${n === min && question.ends ? ` (${question.ends.min})` : ""}${n === max && question.ends ? ` (${question.ends.max})` : ""}`}
            onClick={() => onChange(value === n ? null : n)}
            className={cn("inline-flex size-11 cursor-pointer items-center justify-center rounded-pill border text-body-sm tabular-nums transition-colors", value === n ? "border-primary bg-primary text-on-primary" : "border-hairline-strong bg-surface-card text-ink hover:bg-surface-strong")}
          >
            {n}
          </button>
        ))}
      </div>
      {question.ends && (
        <p aria-hidden="true" className="flex max-w-[30rem] justify-between text-caption text-muted">
          <span>
            {min} = {question.ends.min}
          </span>
          <span>
            {max} = {question.ends.max}
          </span>
        </p>
      )}
    </Group>
  );
}

/** Intended programs: the catalog's checklist, inline in the form, behind "Change" on a panel. */
function ProgramsField({ value, onChange, catalogYear, programNames, layout = "form", label, hint, question }: AnswerControlProps & { label: string; hint: string | null }) {
  const selected = (value as string[] | null) ?? [];
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<string[]>(selected);
  if (layout === "form") {
    return (
      <Group label={label} hint={hint}>
        <div className="max-h-[22rem] overflow-y-auto rounded-[18px] border border-hairline bg-canvas-soft px-4 py-3">
          <ProgramChecklist catalogYear={catalogYear} selected={selected} onChange={(ids) => onChange(ids.slice(0, 8))} />
        </div>
      </Group>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-wrap gap-1.5" aria-label={question.label}>
        {selected.map((p) => (
          <li key={p} className="rounded-pill bg-surface-strong px-3 py-1 text-body-sm text-ink">
            {programNames?.get(p) ?? p}
          </li>
        ))}
      </ul>
      <div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setDraft(selected);
            setOpen(true);
          }}
        >
          {selected.length ? "Change programs" : "Choose programs"}
        </Button>
      </div>
      <Dialog open={open} onClose={() => setOpen(false)} title={question.label} description={question.help ?? undefined}>
        <div className="flex max-h-[55vh] flex-col gap-4 overflow-y-auto pr-1">
          <ProgramChecklist catalogYear={catalogYear} selected={draft} onChange={setDraft} />
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              onChange(draft.slice(0, 8));
              setOpen(false);
            }}
          >
            Save programs
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

/** AP, placement and transfer credits: the planner's credits editor. */
function CreditsField({ value, onChange, catalogYear, label, hint }: AnswerControlProps & { label: string; hint: string | null }) {
  return (
    <Group label={label} hint={hint} as="div">
      <CreditsEditor credits={((value as RecordCredit[] | null) ?? []) as Credit[]} catalogYear={catalogYear} onChange={(credits) => onChange(credits)} />
    </Group>
  );
}

/** Taken courses: a small table (course, quarter, status, optional grade) and a row to add one. */
function TakenCoursesField({ question, set, value, onChange, catalogYear, classYear, label, hint }: AnswerControlProps & { label: string; hint: string | null }) {
  const id = useId();
  const rows = (value as (TakenCourse & { title?: string })[] | null) ?? [];
  const col = (name: string) => question.columns.find((c) => c.id === name);
  const statuses = col("status")?.options ?? ["completed", "in_progress"];
  const terms = termChoices("taken_courses", classYear);
  const [course, setCourse] = useState("");
  const [title, setTitle] = useState("");
  const [pending, setPending] = useState("");
  const [term, setTerm] = useState(terms.find((t) => t.endsWith("-AU")) ?? terms[0] ?? "");
  const [status, setStatus] = useState<TakenCourse["status"]>("completed");
  const [grade, setGrade] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [titles, setTitles] = useState<Record<string, string>>({});

  function add() {
    if (!course) return setError(pending ? "Choose the course from the list." : "Choose a course first.");
    if (rows.some((r) => r.course === course && r.term === term)) return setError(`${course} is already listed for ${termLabel(term)}.`);
    setError(null);
    setTitles((t) => ({ ...t, [course]: title }));
    const kept = status === "in_progress" ? null : grade.trim() || null;
    onChange([...rows.map(strip), { course, term, status, grade: kept, grading: "letter", units: null, locked: false }]);
    setCourse("");
    setTitle("");
    setGrade("");
  }

  return (
    <Group label={label} hint={hint} as="div">
      {rows.length === 0 ? (
        <p className="text-body-sm text-muted">No courses yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-[14px] border border-hairline">
          <table className="w-full border-collapse text-left text-body-sm">
            <caption className="sr-only">{question.label}</caption>
            <thead>
              <tr className="border-b border-hairline bg-canvas-soft">
                {["course", "term", "status", "grade"].map((c) => (
                  <th key={c} scope="col" className="px-3 py-2 text-caption font-medium text-muted">
                    {col(c)?.label ?? c}
                  </th>
                ))}
                <th scope="col" className="px-3 py-2">
                  <span className="sr-only">Remove</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const name = (r as TakenCourseOut).title || titles[r.course];
                return (
                  <tr key={`${r.course}-${r.term}`} className="border-b border-hairline last:border-b-0">
                    <td className="px-3 py-1.5 text-ink">
                      <span className="font-medium tabular-nums">{r.course}</span>
                      {name ? <span className="text-muted"> · {name}</span> : null}
                    </td>
                    <td className="px-3 py-1.5">{termLabel(r.term)}</td>
                    <td className="px-3 py-1.5">{columnLabel(set, "status", r.status ?? "completed")}</td>
                    <td className="px-3 py-1.5 tabular-nums">{r.grade || "—"}</td>
                    <td className="px-1 py-0.5 text-right">
                      <Button variant="ghost" size="sm" className="text-error" aria-label={`Remove ${r.course} (${termLabel(r.term)})`} onClick={() => onChange(rows.filter((_, n) => n !== i).map(strip))}>
                        Remove
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {/* The same box, insets and 44px row button as the credits form (Richard, 2026-11-25). */}
      <div className="@container rounded-lg border border-hairline bg-canvas-soft p-3" role="group" aria-label="Add a course">
        <div className="grid gap-3 @sm:grid-cols-2">
          <div className="@sm:col-span-2">
            <label htmlFor={`${id}-course`} className={labelClass}>
              {col("course")?.label ?? "Course"}
            </label>
            <CoursePicker
              id={`${id}-course`}
              catalogYear={catalogYear}
              value={course}
              onChange={(code, t) => {
                setCourse(code);
                setTitle(t ?? "");
              }}
              onPendingChange={setPending}
              compact
            />
          </div>
          <div>
            <label htmlFor={`${id}-term`} className={labelClass}>
              {col("term")?.label ?? "Quarter"}
            </label>
            <select id={`${id}-term`} className={compact} value={term} onChange={(e) => setTerm(e.target.value)}>
              {terms.map((t) => (
                <option key={t} value={t}>
                  {termLabel(t)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={`${id}-status`} className={labelClass}>
              {col("status")?.label ?? "Status"}
            </label>
            <select
              id={`${id}-status`}
              className={compact}
              value={status}
              onChange={(e) => {
                const next = e.target.value as TakenCourse["status"];
                setStatus(next);
                // A course in progress has no grade yet (Richard, 2026-11-25).
                if (next === "in_progress") setGrade("");
              }}
            >
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {columnLabel(set, "status", s)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={`${id}-grade`} className={labelClass}>
              {col("grade")?.label ?? "Grade (optional)"}
            </label>
            <input
              id={`${id}-grade`}
              className={compact}
              maxLength={4}
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
              placeholder={status === "in_progress" ? "No grade yet" : "e.g. A-"}
              disabled={status === "in_progress"}
            />
          </div>
          <div className="flex items-end">
            <Button type="button" variant="outline" className="min-h-11 w-full border-0 px-4" onClick={add}>
              Add course
            </Button>
          </div>
        </div>
        {error && (
          <p role="alert" className="mt-3 text-caption font-medium text-error">
            {error}
          </p>
        )}
      </div>
    </Group>
  );
}

/** A row as the record stores it. The table shows four columns, but each row also keeps its
 * grading, units and lock from the planner: the whole list is sent on every change, and a
 * rule that needs a letter grade must not count a Pass/Fail course (Blocker 2). */
const strip = (r: TakenCourse & { title?: string }): TakenCourse => ({
  course: r.course,
  term: r.term,
  status: r.status ?? "completed",
  grade: r.status === "in_progress" ? null : (r.grade ?? null),
  grading: r.grading ?? "letter",
  units: r.units ?? null,
  locked: r.locked ?? false,
});

/** Quarters away: "None", or a list of quarters with their reason. */
function TermsAwayField({ question, set, value, onChange, classYear, label, hint }: AnswerControlProps & { label: string; hint: string | null }) {
  const id = useId();
  const rows = (value as TermAway[] | null) ?? null;
  const col = (name: string) => question.columns.find((c) => c.id === name);
  const kinds = (col("kind")?.options ?? ["abroad", "internship", "leave"]) as TermAway["kind"][];
  const terms = termChoices("terms_away", classYear);
  const [term, setTerm] = useState(terms[Math.floor(terms.length / 2)] ?? "");
  const [kind, setKind] = useState<TermAway["kind"]>(kinds[0] ?? "abroad");
  const none = rows !== null && rows.length === 0;
  return (
    <Group label={label} hint={hint} as="div">
      <div>
        <Button type="button" variant="outline" size="sm" aria-pressed={none} className={none ? "bg-primary-wash" : undefined} onClick={() => onChange(none ? null : [])}>
          None
        </Button>
      </div>
      {rows && rows.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {rows.map((r, i) => (
            <li key={`${r.term}-${r.kind}`} className="flex items-center justify-between gap-2 rounded-lg border border-hairline bg-canvas-soft py-0.5 pl-3 pr-1 text-body-sm text-ink">
              <span>
                {termLabel(r.term)} · {columnLabel(set, "away", r.kind)}
              </span>
              <Button variant="ghost" size="sm" className="text-error" aria-label={`Remove ${termLabel(r.term)}`} onClick={() => onChange(rows.filter((_, n) => n !== i))}>
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]" role="group" aria-label="Add a quarter away">
        <div>
          <label htmlFor={`${id}-term`} className={labelClass}>
            {col("term")?.label ?? "Quarter"}
          </label>
          <select id={`${id}-term`} className={compact} value={term} onChange={(e) => setTerm(e.target.value)}>
            {terms.map((t) => (
              <option key={t} value={t}>
                {termLabel(t)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-kind`} className={labelClass}>
            {col("kind")?.label ?? "Reason"}
          </label>
          <select id={`${id}-kind`} className={compact} value={kind} onChange={(e) => setKind(e.target.value as TermAway["kind"])}>
            {kinds.map((k) => (
              <option key={k} value={k}>
                {columnLabel(set, "away", k)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              const list = rows ?? [];
              if (!list.some((r) => r.term === term)) onChange([...list, { term, kind }]);
            }}
          >
            Add quarter
          </Button>
        </div>
      </div>
    </Group>
  );
}
