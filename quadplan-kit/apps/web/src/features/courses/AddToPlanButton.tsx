import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/misc";
import { applyOps } from "@/features/planner/changes";
import { activePlan, newLocalId, today, upsertPlan, type LocalPlan } from "@/features/planner/localPlans";
import { addCourseOps, emptyPlan, ensureIds, newItemId } from "@/features/planner/planModel";
import { TermPickerDialog } from "@/features/planner/TermPickerDialog";
import { termLabel } from "@/features/planner/terms";

/** "Add to plan" for a course page: adds to the active local plan (creating one if needed). */
export function AddToPlanButton({ code, catalogYear }: { code: string; catalogYear: string }) {
  const [open, setOpen] = useState(false);
  const [plan, setPlan] = useState<LocalPlan | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  function start() {
    setPlan(
      activePlan() ?? {
        localId: newLocalId(),
        name: "My Plan",
        isPrimary: true,
        state: emptyPlan(catalogYear),
        updatedDay: today(),
      },
    );
    setOpen(true);
  }

  function pick(term: string) {
    setOpen(false);
    if (!plan) return;
    const r = addCourseOps(code, term);
    if (!r.ok) return;
    const state = applyOps(ensureIds(plan.state), r.ops, { newId: newItemId });
    const stored = upsertPlan({ ...plan, state });
    setMsg(stored ? { ok: true, text: `Added ${code} to ${termLabel(term)}.` } : { ok: false, text: "Could not save: this browser is blocking storage." });
  }

  return (
    <div className="flex flex-col items-start gap-3">
      <Button onClick={start}>Add to plan</Button>
      {msg && (
        <Notice tone={msg.ok ? "success" : "error"} role="status">
          {msg.text}{" "}
          {msg.ok && (
            <Link to="/plan" className="font-medium">
              Open the planner
            </Link>
          )}
        </Notice>
      )}
      {plan && (
        <TermPickerDialog
          open={open}
          title={`Add ${code} to…`}
          plan={plan.state}
          onPick={pick}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}
