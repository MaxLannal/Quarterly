import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { QUARTERS, termAt, termLabel } from "./terms";

interface TermPickerDialogProps {
  open: boolean;
  title: string;
  entryTerm: string;
  years: number;
  /** The item's current term (shown, not selectable). */
  current?: string;
  onPick: (term: string) => void;
  onClose: () => void;
}

/** The keyboard alternative to drag and drop: pick a quarter from a list of buttons. */
export function TermPickerDialog({ open, title, entryTerm, years, current, onPick, onClose }: TermPickerDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title={title} description="Choose a quarter." className="max-w-xl">
      <div className="space-y-4">
        {Array.from({ length: years }, (_, i) => i + 1).map((y) => (
          <fieldset key={y}>
            <legend className="text-caption-uppercase uppercase text-muted">Year {y}</legend>
            <div className="mt-1 grid grid-cols-2 gap-x-1 sm:grid-cols-4">
              {QUARTERS.map((q) => {
                const term = termAt(entryTerm, y, q);
                const isCurrent = term === current;
                return (
                  <Button
                    key={term}
                    variant="outline"
                    disabled={isCurrent}
                    onClick={() => onPick(term)}
                    className="px-2"
                  >
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
