import { useId, useState } from "react";
import type { Goal, Issue, ProgramSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { controlClass, controlCompactClass } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { CAREER_PRESETS, TERM_PRESETS } from "./goals";
import { goalLabel } from "./metrics";
import { planTerms, termLabel } from "./terms";

interface GoalsTabProps {
  goals: Goal[];
  entryTerm: string;
  years: number;
  issues: Issue[];
  programs: ProgramSummary[];
  onChange: (goals: Goal[]) => void;
}

function GoalRow({ goal, issues, onRemove }: { goal: Goal; issues: Issue[]; onRemove: () => void }) {
  const mine = issues.filter((i) => i.goal_id === goal.id);
  return (
    <li className="flex items-start justify-between gap-2 rounded-lg border border-hairline bg-surface-card py-1 pl-3 pr-1 text-body-sm">
      <div className="min-w-0 py-2">
        <div className="text-ink">{goalLabel(goal)}</div>
        {goal.term && <div className="text-caption text-muted">{termLabel(goal.term)}</div>}
        {mine.map((i, n) => (
          <div key={n} className={i.level === "error" ? "mt-1 text-caption text-error" : "mt-1 text-caption text-warning"}>
            {i.message}
          </div>
        ))}
      </div>
      <Button variant="ghost" size="sm" onClick={onRemove} aria-label={`Remove goal: ${goalLabel(goal)}`}>
        Remove
      </Button>
    </li>
  );
}

export function GoalsTab({ goals, entryTerm, years, issues, programs, onChange }: GoalsTabProps) {
  const career = goals.filter((g) => g.scope === "career");
  const perTerm = goals.filter((g) => g.scope === "term");
  const terms = planTerms(entryTerm, years);
  const [preset, setPreset] = useState(TERM_PRESETS[0]?.key ?? "");
  const [term, setTerm] = useState(terms[0] ?? "");
  const presetId = useId();
  const termId = useId();
  const abroad = programs.find((p) => p.type === "study_abroad_block")?.id;
  const remove = (id: string) => onChange(goals.filter((g) => g.id !== id));

  function addTermGoal() {
    const p = TERM_PRESETS.find((x) => x.key === preset);
    const goal = p?.make(term, { studyAbroadProgram: abroad });
    if (goal) onChange([...goals, goal]);
  }

  return (
    <div className="space-y-6">
      <section aria-labelledby="career-goals">
        <h3 id="career-goals" className="text-title-sm">
          Career goals
        </h3>
        {career.length === 0 ? (
          <p className="mt-1 text-body-sm text-muted">None yet.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {career.map((g) => (
              <GoalRow key={g.id} goal={g} issues={issues} onRemove={() => remove(g.id)} />
            ))}
          </ul>
        )}
        <div className="mt-2 flex flex-wrap gap-x-1">
          {CAREER_PRESETS.map((p) => (
            <Button key={p.key} variant="outline" size="sm" onClick={() => onChange([...goals, ...p.make(entryTerm)])}>
              + {p.label}
            </Button>
          ))}
        </div>
      </section>
      <section aria-labelledby="term-goals">
        <h3 id="term-goals" className="text-title-sm">
          Quarter goals
        </h3>
        {perTerm.length === 0 ? (
          <p className="mt-1 text-body-sm text-muted">None yet.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {perTerm.map((g) => (
              <GoalRow key={g.id} goal={g} issues={issues} onRemove={() => remove(g.id)} />
            ))}
          </ul>
        )}
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <div>
            <label htmlFor={presetId} className="mb-1.5 block text-caption font-medium text-ink">
              Goal
            </label>
            <select id={presetId} value={preset} onChange={(e) => setPreset(e.target.value)} className={cn(controlClass, controlCompactClass)}>
              {TERM_PRESETS.map((p) => (
                <option key={p.key} value={p.key} disabled={p.key === "study_abroad" && !abroad}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={termId} className="mb-1.5 block text-caption font-medium text-ink">
              Quarter
            </label>
            <select id={termId} value={term} onChange={(e) => setTerm(e.target.value)} className={cn(controlClass, controlCompactClass)}>
              {terms.map((t) => (
                <option key={t} value={t}>
                  {termLabel(t)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <Button variant="outline" className="mt-2" onClick={addTermGoal}>
          Add quarter goal
        </Button>
      </section>
    </div>
  );
}
