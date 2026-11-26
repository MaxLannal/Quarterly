import { Badge } from "@/components/ui/misc";
import { usePlanner } from "@/features/planner/context";
import { cn } from "@/lib/utils";
import type { ProposedBlock } from "./proposals";

/**
 * A course the planner agent proposes (issue #18): a dashed block in its quarter, until the
 * student accepts or rejects its group. Clicking it selects the proposal in the panel. The
 * walkthrough lights its group with `glow-ring`.
 */
export function ProposalBlock({ block }: { block: ProposedBlock }) {
  const { courses, proposalTitles, glow, selectProposal } = usePlanner();
  const title = proposalTitles.get(block.proposalId) ?? "the planner's proposal";
  const course = courses.get(block.course);
  const lit = glow.has(block.proposalId);
  return (
    <li>
      <button
        type="button"
        data-testid="proposal-block"
        data-proposal={block.proposalId}
        data-glow={lit ? "true" : undefined}
        aria-label={`${block.course}, proposed in ${title}`}
        onClick={() => selectProposal(block.proposalId)}
        className={cn(
          "flex min-h-11 w-full animate-settle flex-col rounded-lg border-2 border-dashed border-primary/50 bg-primary-wash/60 px-3 py-1.5 text-left text-caption text-ink transition-shadow hover:shadow-hover",
          lit && "glow-ring border-solid border-primary",
        )}
      >
        <span className="flex flex-wrap items-center gap-x-2">
          <span className="font-medium tabular-nums">{block.course}</span>
          <Badge casing="normal" className="px-2 py-0">
            {block.action === "move-in" ? "Proposed: move here" : "Proposed"}
          </Badge>
        </span>
        {course?.title && <span className="truncate text-body">{course.title}</span>}
      </button>
    </li>
  );
}
