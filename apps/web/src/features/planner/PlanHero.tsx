import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { PencilIcon } from "@/components/ui/icons";
import { controlClass, controlCompactClass, Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { isBefore, MAX_PLAN_YEARS, termAt, termLabel } from "./terms";

/** The plan's name as the page's headline, with a pencil to rename it (FEEDBACK 2026-11-16). */
function PlanName({ name, onRename }: { name: string; onRename: (name: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const input = useRef<HTMLInputElement>(null);
  const inputId = useId();
  useEffect(() => {
    if (editing) input.current?.select();
  }, [editing]);
  if (editing) {
    const commit = () => {
      const next = draft.trim();
      if (next && next !== name) onRename(next);
      setEditing(false);
    };
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          commit();
        }}
      >
        <label htmlFor={inputId} className="sr-only">
          Plan name
        </label>
        <Input
          ref={input}
          id={inputId}
          value={draft}
          maxLength={80}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setDraft(name);
              setEditing(false);
            }
          }}
          className="w-[28rem] max-w-full font-display text-display-sm"
        />
      </form>
    );
  }
  return (
    <div className="group flex min-w-0 items-center gap-1">
      <h2 className="planner-title truncate font-display text-display-md sm:text-display-lg">{name || "My Plan"}</h2>
      <button
        type="button"
        aria-label="Rename plan"
        onClick={() => {
          setDraft(name);
          setEditing(true);
        }}
        className="flex size-11 shrink-0 items-center justify-center rounded-pill text-gray-dark transition-[color,background-color] duration-300 hover:bg-white/[0.06] hover:text-ink"
      >
        <PencilIcon size={18} />
      </button>
    </div>
  );
}

/**
 * The graduation quarter as one of the plan's facts, with a pencil (D8, FEEDBACK "Minor design
 * changes"). The pencil opens the quarter list in place; choosing one applies it, Escape or
 * leaving the list keeps the old one.
 */
function GraduationField({ value, choices, onChange }: { value: string; choices: string[]; onChange: (term: string) => void }) {
  const [editing, setEditing] = useState(false);
  const selectId = useId();
  const select = useRef<HTMLSelectElement>(null);
  const pencil = useRef<HTMLButtonElement>(null);
  const wasEditing = useRef(false);
  useEffect(() => {
    if (editing) select.current?.focus();
    else if (wasEditing.current) pencil.current?.focus();
    wasEditing.current = editing;
  }, [editing]);
  if (editing) {
    return (
      <div className="flex items-center gap-2">
        <label htmlFor={selectId} className="mono-label text-muted">
          Graduating in
        </label>
        <select
          ref={select}
          id={selectId}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setEditing(false);
          }}
          onBlur={() => setEditing(false)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setEditing(false);
          }}
          className={cn(controlClass, controlCompactClass, "w-44 text-caption pointer-coarse:text-body-md")}
        >
          {choices.map((t) => (
            <option key={t} value={t}>
              {termLabel(t)}
            </option>
          ))}
        </select>
      </div>
    );
  }
  return (
    <div className="flex items-center" data-testid="graduation" data-term={value}>
      <span className="mono-label text-muted">
        Graduating in <span className="text-ink">{termLabel(value)}</span>
      </span>
      <button
        ref={pencil}
        type="button"
        aria-label={`Change graduation quarter (${termLabel(value)})`}
        onClick={() => setEditing(true)}
        className="-my-2 flex size-11 shrink-0 items-center justify-center rounded-pill text-gray-dark transition-[color,background-color] duration-300 hover:bg-white/[0.06] hover:text-ink"
      >
        <PencilIcon size={14} />
      </button>
    </div>
  );
}

/** Graduation choices: Autumn, Winter and Spring from the first quarter to one year past the
 * last, never past the longest plan the API accepts. */
export function graduationChoices(entryTerm: string, years: number): string[] {
  const out: string[] = [];
  for (let y = 1; y <= Math.min(years + 1, MAX_PLAN_YEARS); y += 1) {
    for (const q of ["AU", "WI", "SP"] as const) {
      const t = termAt(entryTerm, y, q);
      if (!isBefore(t, entryTerm)) out.push(t);
    }
  }
  return out;
}

/** A thin separator between two facts in the mono line. */
const Sep = () => (
  <span aria-hidden="true" className="planner-fact-sep">
    ·
  </span>
);

interface PlanHeroProps {
  name: string;
  onRename: (name: string) => void;
  /** The plan check's verdict, a luminous chip beside the name (PL-1, D11). */
  verdict: ReactNode;
  catalogYear: string;
  years: number;
  units: string;
  courses: number;
  graduation: string;
  graduationChoices: string[];
  onGraduation: (term: string) => void;
  /** The plan's programs and the "+ Program" button. */
  programs: ReactNode;
}

/**
 * The planner's headline (docs/DESIGN.md "Dark glass"): a mono eyebrow, the plan's name in the
 * display serif with its verdict, then one mono line of facts (catalog year, length, units,
 * courses, graduation). The programs sit at the right on a wide screen, below on a phone.
 */
export function PlanHero({ name, onRename, verdict, catalogYear, years, units, courses, graduation, graduationChoices: choices, onGraduation, programs }: PlanHeroProps) {
  return (
    <header className="planner-hero grid gap-x-10 gap-y-6 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
      <div className="flex min-w-0 flex-col gap-2.5">
        <p className="mono-label flex items-center gap-2 text-muted">
          <span aria-hidden="true" className="planner-eyebrow-dot" />
          Planner
          <span aria-hidden="true" className="hidden text-muted sm:inline">
            {"//"}
          </span>
          <span className="hidden sm:inline">Four years, quarter by quarter</span>
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
          <PlanName name={name} onRename={onRename} />
          {verdict}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="mono-label text-muted">Catalog {catalogYear}</span>
          <Sep />
          <span className="mono-label text-muted">
            {years} year{years === 1 ? "" : "s"}
          </span>
          <Sep />
          <span className="mono-label text-muted">{units} units</span>
          <Sep />
          <span className="mono-label text-muted">
            {courses} course{courses === 1 ? "" : "s"}
          </span>
          <Sep />
          <GraduationField value={graduation} choices={choices} onChange={onGraduation} />
        </div>
      </div>
      <div className="flex min-w-0 flex-col gap-2 xl:items-end">
        <span className="mono-label text-muted">Programs</span>
        {programs}
        <p className="text-caption text-muted">Not official advising. Confirm with your adviser and My Planner.</p>
      </div>
    </header>
  );
}
