import { useDraggable } from "@dnd-kit/core";
import { useState } from "react";
import { useEligible } from "@/api/hooks";
import type { CourseSummary, NodeProgress, ProgramDetail } from "@/api/types";
import { isNotAvailable } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Badge, NotAvailable, Spinner } from "@/components/ui/misc";
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
        className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-200"
      >
        <div className={cn("h-full", p.satisfied ? "bg-green-700" : "bg-blue-700")} style={{ width: `${pct}%` }} />
      </div>
      <span className="shrink-0 text-xs text-muted-foreground">
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
      className={cn("flex items-center rounded-md border border-border bg-background text-sm", isDragging && "z-30 shadow-lg")}
    >
      <button
        type="button"
        aria-label={`Drag ${course.code} onto the plan`}
        className="flex min-h-11 w-8 shrink-0 cursor-grab touch-none items-center justify-center text-muted-foreground"
        {...attributes}
        {...listeners}
      >
        <span aria-hidden="true">⠿</span>
      </button>
      <div className="min-w-0 flex-1 py-1">
        <div className="font-medium">{course.code}</div>
        <div className="truncate text-xs text-muted-foreground">
          {course.title}
          {hours ? ` · ${round1(hours.value)} h/wk` : ""}
        </div>
      </div>
      <Button variant="ghost" className="px-2" onClick={() => openAddTo(course.code)} aria-label={`Add ${course.code} to a quarter`}>
        Add
      </Button>
    </li>
  );
}

function EligibleList({ programId, node, catalogYear }: { programId: string; node: string; catalogYear: string }) {
  const q = useEligible(programId, node, catalogYear);
  if (q.isLoading) return <Spinner label="Loading eligible courses" />;
  if (q.error) return isNotAvailable(q.error) ? <NotAvailable feature="Eligible courses" /> : <p className="text-sm text-red-800">Could not load eligible courses.</p>;
  if (!q.data?.length) return <p className="text-sm text-muted-foreground">No eligible courses listed.</p>;
  return (
    <ul className="mt-1 space-y-1" aria-label="Eligible courses">
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
    <li className="py-1">
      <div className="flex items-start gap-1">
        {hasChildren ? (
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${entry.label}`}
            onClick={() => toggle(entry.path)}
            className="flex min-h-11 min-w-11 items-center justify-center rounded-md hover:bg-muted"
          >
            <span aria-hidden="true">{expanded ? "▾" : "▸"}</span>
          </button>
        ) : (
          <span className="w-11 shrink-0" aria-hidden="true" />
        )}
        <div className="min-w-0 flex-1">
          {entry.selectable ? (
            <button
              type="button"
              aria-expanded={isActive}
              onClick={() => setActive(isActive ? null : entry.path)}
              className="min-h-11 w-full rounded-md px-1 text-left text-sm hover:bg-muted"
            >
              <span className="font-medium">{entry.label}</span>
              <span className="block text-xs text-muted-foreground">{describe(entry)}</span>
            </button>
          ) : (
            <div className="px-1 py-2 text-sm">
              <span className="font-medium">{entry.label}</span>
              <span className="block text-xs text-muted-foreground">{describe(entry)}</span>
            </div>
          )}
          <ProgressBar p={p} label={entry.label} />
          {isActive && <EligibleList programId={programId} node={entry.path} catalogYear={catalogYear} />}
        </div>
      </div>
      {hasChildren && expanded && (
        <ul className="ml-4 border-l border-border pl-1">
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
    <section aria-label={program.name} className={cn("rounded-lg border border-l-4 border-border p-2", REQUIREMENT_COLORS[index % REQUIREMENT_COLORS.length])}>
      <h3 className="flex flex-wrap items-center gap-2 font-semibold">
        {program.name}
        {program.status !== "published" && <Badge tone="amber">In review</Badge>}
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
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Requirements</h2>
        <Button variant="outline" onClick={onAddProgram}>
          Add program
        </Button>
      </div>
      {details.length === 0 && <p className="text-sm text-muted-foreground">Add a program to see its requirements and track progress.</p>}
      {details.map((d, i) =>
        d.isLoading ? (
          <Spinner key={d.id} label={`Loading ${d.id}`} />
        ) : d.data ? (
          <ProgramTree key={d.id} program={d.data} index={i} progress={byNode} />
        ) : (
          <p key={d.id} className="text-sm text-red-800">
            {isNotAvailable(d.error) ? `Program ${d.id} is not available yet.` : `Could not load program ${d.id}.`}
          </p>
        ),
      )}
    </div>
  );
}
