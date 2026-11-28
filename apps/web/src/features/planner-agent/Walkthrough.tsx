import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { PlannerRun } from "./usePlannerRun";
import type { Walkthrough as Walk } from "./useWalkthrough";

/**
 * The walkthrough of a first plan (issue #18; Max, 2026-11-27: "no need to accept/reject one by
 * one … walk through the main sequences one by one, highlight the sequence, and generate a
 * paragraph on what the sequence is about, then the student clicks next"). One sequence at a
 * time: the grid lights its courses, and the card holds only the sequence's name and its
 * paragraph (what it is about, why it suits this student). Back and Next move along. Nothing is
 * accepted per step: "Keep this plan" applies every sequence at once (applying stays the
 * student's action), and the tour can end without it (the plan stays proposed on the grid).
 */
export function Walkthrough({ walk, run }: { walk: Walk; run: PlannerRun }) {
  const ref = useRef<HTMLElement>(null);
  const [keeping, setKeeping] = useState(false);
  const p = walk.current;
  useEffect(() => {
    // The card sits above the conversation: bring it into view (the chat may be scrolled down to
    // the plan card that started the tour), then move focus to it.
    ref.current?.scrollIntoView?.({ block: "start" });
    ref.current?.focus({ preventScroll: true });
  }, [walk.step]);
  if (walk.step === null) return null;

  async function keep() {
    setKeeping(true);
    try {
      for (const g of walk.groups) await run.accept(g.id);
    } finally {
      setKeeping(false);
      walk.stop();
    }
  }

  const keepButton = (primary: boolean) => (
    <Button variant={primary ? "primary" : "outline"} size="sm" onClick={() => void keep()} disabled={keeping || run.running}>
      {keeping ? "Keeping…" : "Keep this plan"}
    </Button>
  );

  return (
    <section
      ref={ref}
      tabIndex={-1}
      aria-label="Walkthrough of your plan"
      className="mb-4 rounded-xl border border-hairline bg-canvas p-4 shadow-[0_1px_2px_rgb(17_17_17/0.04)] focus-visible:outline-2 focus-visible:outline-ink"
      data-testid="walkthrough"
    >
      {p ? (
        <article aria-label={`Walkthrough: ${p.title}`} className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-caption font-semibold text-muted">
              Sequence {walk.step + 1} of {walk.total}
            </p>
            <span aria-hidden="true" className="flex flex-wrap justify-end gap-1">
              {Array.from({ length: walk.total }, (_, i) => (
                <span key={i} className={i === walk.step ? "h-1.5 w-4 rounded-pill bg-ink" : "h-1.5 w-1.5 rounded-pill bg-hairline-strong"} />
              ))}
            </span>
          </div>
          <h3 className="text-title-md">{p.title}</h3>
          {p.members.length === 1 ? (
            p.members[0]?.why && <p className="text-body-sm leading-relaxed text-body">{p.members[0].why}</p>
          ) : (
            // The last step gathers the single courses and electives: a short note for each.
            <ul className="flex flex-col gap-3">
              {p.members.map((m) => (
                <li key={m.id} className="text-body-sm leading-relaxed text-body">
                  <span className="font-semibold text-ink">{m.title}. </span>
                  {m.why}
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-center gap-2 border-t border-hairline pt-3">
            <Button variant="outline" size="sm" onClick={walk.back} disabled={walk.step === 0}>
              Back
            </Button>
            <Button size="sm" onClick={walk.next}>
              Next
            </Button>
            <span className="flex-1" />
            {keepButton(false)}
            <Button variant="ghost" size="sm" onClick={walk.stop}>
              Skip tour
            </Button>
          </div>
        </article>
      ) : (
        <div className="flex flex-col gap-2 text-body-sm">
          <p className="font-semibold text-ink">That's the whole plan.</p>
          <p className="text-body">Keep it to make it yours, or tell me below what to change. Until you keep it, it stays on the grid as a proposal.</p>
          <div className="flex flex-wrap gap-2 pt-1">
            {keepButton(true)}
            <Button variant="outline" size="sm" onClick={walk.back} disabled={walk.total === 0}>
              Back
            </Button>
            <Button variant="ghost" size="sm" onClick={walk.stop}>
              Done
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
