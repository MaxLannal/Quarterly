import type { PlanState } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { academicYear, academicYearLabel, classYearLabel, graduationTerm, planTerms, termLabel, yearIndex } from "./terms";

interface TermPickerDialogProps {
  open: boolean;
  title: string;
  plan: Pick<PlanState, "entry_term" | "entry_year_level" | "graduation_term">;
  /** The item's current term (shown, not selectable). */
  current?: string;
  onPick: (term: string) => void;
  onClose: () => void;
}

/** The keyboard alternative to drag and drop: pick a quarter from a list of buttons, grouped by year. */
export function TermPickerDialog({ open, title, plan, current, onPick, onClose }: TermPickerDialogProps) {
  const terms = planTerms(plan.entry_term, graduationTerm(plan));
  const years = new Map<number, string[]>();
  for (const t of terms) {
    const y = yearIndex(t, plan.entry_term);
    years.set(y, [...(years.get(y) ?? []), t]);
  }
  return (
    <Dialog open={open} onClose={onClose} title={title} className="max-w-xl">
      <div className="space-y-4">
        {[...years].map(([y, ts]) => (
          <fieldset key={y}>
            <legend className="text-caption-uppercase uppercase text-muted">
              {classYearLabel(y, plan.entry_year_level ?? 1)} · {academicYearLabel(academicYear(ts[0] ?? plan.entry_term))}
            </legend>
            <div className="mt-1 grid grid-cols-2 gap-x-1 sm:grid-cols-4">
              {ts.map((term) => {
                const isCurrent = term === current;
                return (
                  <Button key={term} variant="outline" disabled={isCurrent} onClick={() => onPick(term)} className="px-2">
                    {termLabel(term)}
                    {isCurrent && <span className="sr-only"> (current)</span>}
                  </Button>
                );
              })}
            </div>
          </fieldset>
        ))}
      </div>
    </Dialog>
  );
}
