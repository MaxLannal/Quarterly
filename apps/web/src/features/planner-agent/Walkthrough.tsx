import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { PlannerProposalCard } from "./PlannerProposalCard";
import type { PlannerRun } from "./usePlannerRun";
import type { Walkthrough as Walk } from "./useWalkthrough";

/**
 * The walkthrough card (issue #18): "Step n of N", the current group with why it suits the
 * student, Accept / Reject (each moves on) and Back / Next / Skip tour. Focus stays on the card.
 */
export function Walkthrough({ walk, run }: { walk: Walk; run: PlannerRun }) {
  const ref = useRef<HTMLElement>(null);
  const p = walk.current;
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, [walk.step]);
  if (walk.step === null) return null;
  return (
    <section ref={ref} tabIndex={-1} aria-label="Walkthrough of your plan" className="mb-4 rounded-xl border-2 border-primary/40 bg-primary-wash/40 p-3 focus-visible:outline-2 focus-visible:outline-primary" data-testid="walkthrough">
      {p ? (
        <>
          <p className="mb-2 text-caption-uppercase uppercase text-primary">
            Step {walk.step + 1} of {walk.total}
          </p>
          <PlannerProposalCard
            proposal={p}
            label={`Walkthrough: ${p.title}`}
            onAccept={() => void run.accept(p.id)}
            onReject={() => void run.reject(p.id)}
            onAskAgain={() => run.askAgain(p.id)}
            footer={
              <div className="mt-3 flex flex-wrap gap-2 border-t border-hairline pt-3">
                <Button variant="outline" size="sm" onClick={walk.back} disabled={walk.step === 0}>
                  Back
                </Button>
                <Button variant="outline" size="sm" onClick={walk.next}>
                  Next
                </Button>
                <Button variant="ghost" size="sm" onClick={walk.stop}>
                  Skip tour
                </Button>
              </div>
            }
          />
        </>
      ) : (
        <div className="space-y-2 p-1 text-body-sm">
          <p className="font-medium text-ink">That's the whole plan.</p>
          <p className="text-body">Accept or reject what is left below, or tell me what to change.</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={walk.back} disabled={walk.total === 0}>
              Back
            </Button>
            <Button size="sm" onClick={walk.stop}>
              Done
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
