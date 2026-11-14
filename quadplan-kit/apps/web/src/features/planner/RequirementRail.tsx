import { useDraggable } from "@dnd-kit/core";
import { useState } from "react";
import { useEligible } from "@/api/hooks";
import type { CourseSummary, NodeProgress, ProgramDetail } from "@/api/types";
import { isNotAvailable } from "@/api/client";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/layout/page";
import { ChevronIcon, GripIcon } from "@/components/ui/icons";
import { Badge, ErrorText, NotAvailable, Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { describe, progressByNode, ruleTree, type RuleEntry } from "@/features/programs/rules";
import { REQUIREMENT_COLORS, usePlanner } from "./context";
import { attribute, round1 } from "./metrics";

function ProgressBar({ p, label }: { p: NodeProgress | undefined; label: string }) {
  if (!p) return null;
  const pct = p.need > 0 ? Math.min(100, Math.round((p.have / p.need) * 100)) : 100;
  return (
    <div className="mt-1 flex items-center gap-2">
      <div
        role="progressbar"
        aria-label={`${label} progress`}
        aria-valuemin={0}
        aria-valuemax={p.need}
        aria-valuenow={Math.min(p.have, p.need)}
        aria-valuetext={`${p.have} of ${p.need} ${p.unit}`}
        className="h-1.5 flex-1 overflow-hidden rounded-pill bg-surface-strong"
      >
        <div className={cn("h-full rounded-pill", p.satisfied ? "bg-success" : "bg-primary")} style={{ width: `${pct}%` }} />
      </div>
      <span className="shrink-0 text-caption tabular-nums text-muted">
        {p.have}/{p.need}
      </span>
    </div>
  );
}

function EligibleCourse({ course }: { course: CourseSummary }) {
  const { openAddTo } = usePlanner();
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `new:${course.code}`,
    data: { kind: "course", code: course.code },
  });
  const hours = attribute(course, "workload_hours");
  return (
    <li
      ref={setNodeRef}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined}
      className={cn("flex items-center rounded-lg border border-hairline bg-surface-card text-caption transition-shadow hover:shadow-hover", isDragging && "z-30 shadow-overlay")}
    >
      <button
        type="button"
        aria-label={`Drag ${course.code} onto the plan`}
        className="flex min-h-11 w-11 shrink-0 cursor-grab touch-none items-center justify-center rounded-l-md text-gray-dark hover:text-ink focus-visible:outline-offset-[-2px]"
        {...attributes}
        {...listeners}
      >
        <GripIcon size={14} />
      </button>
      <div className="min-w-0 flex-1 py-1.5">
        <div className="whitespace-nowrap font-medium tabular-nums text-ink">{course.code}</div>
        <div className="truncate text-caption text-muted">
          {course.title}
          {hours ? ` · ${round1(hours.value)} h/wk` : ""}
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={() => openAddTo(course.code)} aria-label={`Add ${course.code} to a quarter`}>
        Add
      </Button>
    </li>
  );
}

function EligibleList({ programId, node, catalogYear }: { programId: string; node: string; catalogYear: string }) {
  const q = useEligible(programId, node, catalogYear);
  if (q.isLoading) return <Spinner label="Loading eligible courses" />;
  if (q.error) return isNotAvailable(q.error) ? <NotAvailable feature="Eligible courses" /> : <ErrorText>Could not load eligible courses.</ErrorText>;
  if (!q.data?.length) return <p className="text-body-sm text-muted">No eligible courses listed.</p>;
  return (
    <ul className="mt-2 space-y-1.5" aria-label="Eligible courses">
      {q.data.map((c) => (
        <EligibleCourse key={c.code} course={c} />
      ))}
    </ul>
  );
}

function RuleRow({
  entry,
  programId,
  progress,
  open,
  toggle,
  active,
  setActive,
  catalogYear,
}: {
  entry: RuleEntry;
  programId: string;
  progress: Map<string, NodeProgress>;
  open: Set<string>;
  toggle: (path: string) => void;
  active: string | null;
  setActive: (path: string | null) => void;
  catalogYear: string;
}) {
  const p = progress.get(entry.path);
  const hasChildren = entry.children.length > 0;
  const expanded = open.has(entry.path);
  const isActive = active === entry.path;
  return (
    <li className="py-0.5">
      <div className="flex items-start gap-0.5">
        {hasChildren ? (
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${entry.label}`}
            onClick={() => toggle(entry.path)}
            className="flex min-h-11 min-w-11 shrink-0 cursor-pointer items-center justify-center rounded-pill text-gray-dark hover:bg-surface-strong hover:text-ink focus-visible:outline-offset-[-2px]"
          >
            <ChevronIcon open={expanded} />
          </button>
        ) : (
          <span className="w-3 shrink-0" aria-hidden="true" />
        )}
        <div className="min-w-0 flex-1">
          {entry.selectable ? (
            <button
              type="button"
              aria-expanded={isActive}
              onClick={() => setActive(isActive ? null : entry.path)}
              className={cn(
                "min-h-11 w-full cursor-pointer rounded-md px-2 py-1.5 text-left text-body-sm hover:bg-surface-strong focus-visible:outline-offset-0",
                isActive && "bg-primary-wash hover:bg-primary-wash",
              )}
            >
              <span className="font-medium text-ink">{entry.label}</span>
              <span className="block text-caption text-muted">{describe(entry)}</span>
            </button>
          ) : (
            <div className="px-2 py-2.5 text-body-sm">
              <span className="font-medium text-ink">{entry.label}</span>
              <span className="block text-caption text-muted">{describe(entry)}</span>
            </div>
          )}
          <ProgressBar p={p} label={entry.label} />
          {isActive && <EligibleList programId={programId} node={entry.path} catalogYear={catalogYear} />}
        </div>
      </div>
      {hasChildren && expanded && (
        <ul className="ml-3 border-l border-hairline">
          {entry.children.map((c) => (
            <RuleRow
              key={c.path}
              entry={c}
              programId={programId}
              progress={progress}
              open={open}
              toggle={toggle}
              active={active}
              setActive={setActive}
              catalogYear={catalogYear}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function ProgramTree({ program, index, progress }: { program: ProgramDetail; index: number; progress: Map<string, NodeProgress> }) {
  const tree = ruleTree(program.id, program.rules);
  const [open, setOpen] = useState<Set<string>>(() => new Set([tree.path]));
  const [active, setActive] = useState<string | null>(null);
  const toggle = (path: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(path)) n.delete(path);
      else n.add(path);
      return n;
    });
  return (
    <section aria-label={program.name} className={cn("rounded-lg border border-l-[3px] border-hairline bg-canvas-soft p-2", REQUIREMENT_COLORS[index % REQUIREMENT_COLORS.length])}>
      <h3 className="flex flex-wrap items-center gap-2 px-2 pt-1 text-title-sm">
        {program.name}
        {program.status !== "published" && <Badge tone="warning">In review</Badge>}
      </h3>
      <ul>
        <RuleRow
          entry={{ ...tree, label: "All requirements" }}
          programId={program.id}
          progress={progress}
          open={open}
          toggle={toggle}
          active={active}
          setActive={setActive}
          catalogYear={program.catalog_year}
        />
      </ul>
    </section>
  );
}

interface RequirementRailProps {
  details: { data?: ProgramDetail; error: unknown; isLoading: boolean; id: string }[];
  progress: NodeProgress[] | undefined;
  onAddProgram: () => void;
}

export function RequirementRail({ details, progress, onAddProgram }: RequirementRailProps) {
  const byNode = progressByNode(progress);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-display text-display-sm">Requirements</h2>
        <Button variant="outline" size="sm" onClick={onAddProgram}>
          Add program
        </Button>
      </div>
      {details.length === 0 && <EmptyState>Add a program to see its requirements and track progress.</EmptyState>}
      {details.map((d, i) =>
        d.isLoading ? (
          <Spinner key={d.id} label={`Loading ${d.id}`} />
        ) : d.data ? (
          <ProgramTree key={d.id} program={d.data} index={i} progress={byNode} />
        ) : (
          <ErrorText key={d.id}>{isNotAvailable(d.error) ? `Program ${d.id} is not available yet.` : `Could not load program ${d.id}.`}</ErrorText>
        ),
      )}
    </div>
  );
}
