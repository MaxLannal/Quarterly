import { useDraggable } from "@dnd-kit/core";
import { useState } from "react";
import { useEligible } from "@/api/hooks";
import type { CourseSummary, NodeProgress, ProgramDetail } from "@/api/types";
import { isNotAvailable } from "@/api/client";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/layout/page";
import { CheckIcon, ChevronIcon, GripIcon } from "@/components/ui/icons";
import { Badge, ErrorText, NotAvailable, Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { describe, progressByNode, ruleTree, type RuleEntry } from "@/features/programs/rules";
import { STRIP_CLASSES, stripKind, usePlanner, type StripKind } from "./context";
import { termLabel } from "./terms";

/** Subtle progress: "3 of 5", with a check once the node is met (FEEDBACK F4: no alarm). */
function Progress({ p }: { p: NodeProgress | undefined }) {
  if (!p) return null;
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1 text-caption tabular-nums", p.satisfied ? "text-success" : "text-muted")} data-testid="node-progress">
      {p.satisfied && <CheckIcon size={14} />}
      {Math.min(p.have, p.need)} of {p.need}
      <span className="sr-only"> {p.unit}</span>
    </span>
  );
}

/** One course in the tree: code in bold, name in small text; drag it or press Add. */
function TreeCourse({ course }: { course: CourseSummary }) {
  const { openAddTo, plan } = usePlanner();
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `new:${course.code}`,
    data: { kind: "course", code: course.code },
  });
  const placed = (plan.items ?? []).find((i) => i.course === course.code);
  return (
    <li
      ref={setNodeRef}
      data-testid="tree-course"
      className={cn("flex animate-rise items-center rounded-md transition-colors hover:bg-canvas-soft", isDragging && "opacity-40")}
    >
      <button
        type="button"
        aria-label={`Drag ${course.code} onto the plan`}
        className="flex size-11 shrink-0 cursor-grab touch-none items-center justify-center rounded-md text-gray-dark hover:text-ink focus-visible:outline-offset-[-2px]"
        {...attributes}
        {...listeners}
      >
        <GripIcon size={14} />
      </button>
      <div className="min-w-0 flex-1 py-1">
        <div className="whitespace-nowrap text-body-sm font-semibold tabular-nums text-ink">{course.code}</div>
        <div className="truncate text-caption text-muted" title={course.title}>
          {course.title}
        </div>
      </div>
      {placed && (
        <span className="shrink-0 text-success" title={`On your plan: ${termLabel(placed.term)}`}>
          <CheckIcon size={14} />
          <span className="sr-only">On your plan, {termLabel(placed.term)}</span>
        </span>
      )}
      <Button variant="ghost" size="sm" onClick={() => openAddTo(course.code)} aria-label={`Add ${course.code} to a quarter`}>
        Add
      </Button>
    </li>
  );
}

function TreeCourses({ programId, node, catalogYear }: { programId: string; node: string; catalogYear: string }) {
  const q = useEligible(programId, node, catalogYear);
  if (q.isLoading) return <Spinner label="Loading courses" />;
  if (q.error) return isNotAvailable(q.error) ? <NotAvailable feature="Eligible courses" /> : <ErrorText>Could not load eligible courses.</ErrorText>;
  if (!q.data?.length) return <p className="py-2 text-caption text-muted">No eligible courses listed.</p>;
  return (
    <ul className="flex flex-col" aria-label="Eligible courses">
      {q.data.map((c) => (
        <TreeCourse key={c.code} course={c} />
      ))}
    </ul>
  );
}

interface NodeProps {
  entry: RuleEntry;
  programId: string;
  catalogYear: string;
  progress: Map<string, NodeProgress>;
  open: Set<string>;
  toggle: (path: string) => void;
}

/** A requirement node: a disclosure button (label, rule in small text, progress) over its children or its courses. */
function TreeNode({ entry, programId, catalogYear, progress, open, toggle }: NodeProps) {
  const expanded = open.has(entry.path);
  const hasChildren = entry.children.length > 0;
  return (
    <li>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => toggle(entry.path)}
        className="flex min-h-11 w-full cursor-pointer items-start gap-1.5 rounded-md py-1.5 pl-1 pr-2 text-left transition-colors hover:bg-canvas-soft focus-visible:outline-offset-0"
      >
        <span className="mt-0.5 shrink-0 text-gray-dark">
          <ChevronIcon open={expanded} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-body-sm font-medium text-ink">{entry.label}</span>
          <span className="block text-caption text-muted">{describe(entry)}</span>
        </span>
        <Progress p={progress.get(entry.path)} />
      </button>
      {expanded && (
        <div className="ml-[13px] animate-fade-in border-l border-hairline pl-2">
          {hasChildren ? (
            <ul className="flex flex-col">
              {entry.children.map((c) => (
                <TreeNode key={c.path} entry={c} programId={programId} catalogYear={catalogYear} progress={progress} open={open} toggle={toggle} />
              ))}
            </ul>
          ) : (
            <TreeCourses programId={programId} node={entry.path} catalogYear={catalogYear} />
          )}
        </div>
      )}
    </li>
  );
}

/** Group nodes start open so the structure shows; course lists load when a node is opened. */
function initiallyOpen(entry: RuleEntry, out = new Set<string>()): Set<string> {
  if (entry.children.length > 0) {
    out.add(entry.path);
    entry.children.forEach((c) => initiallyOpen(c, out));
  }
  return out;
}

function ProgramTree({ program, kind, progress }: { program: ProgramDetail; kind: StripKind; progress: Map<string, NodeProgress> }) {
  const tree = ruleTree(program.id, program.rules);
  const [open, setOpen] = useState<Set<string>>(() => initiallyOpen(tree));
  const toggle = (path: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(path)) n.delete(path);
      else n.add(path);
      return n;
    });
  // The root is the program itself: its children are the tree's first level.
  const top = tree.children.length > 0 ? tree.children : [tree];
  return (
    <section aria-label={program.name} className={cn("border-l-[3px] pl-3", STRIP_CLASSES[kind])} data-kind={kind}>
      <h3 className="flex flex-wrap items-center gap-x-2 gap-y-1 text-title-sm">
        <span className="min-w-0 flex-1">{program.name}</span>
        {program.status !== "published" && <Badge tone="warning" casing="normal">Not yet hand-checked</Badge>}
        <Progress p={progress.get(tree.path)} />
      </h3>
      <ul className="mt-1 flex flex-col">
        {top.map((e) => (
          <TreeNode key={e.path} entry={e} programId={program.id} catalogYear={program.catalog_year} progress={progress} open={open} toggle={toggle} />
        ))}
      </ul>
    </section>
  );
}

interface RequirementTreeProps {
  details: { data?: ProgramDetail; error: unknown; isLoading: boolean; id: string }[];
  progress: NodeProgress[] | undefined;
  onAddProgram: () => void;
}

/** Program requirements as a vertical tree: program, its nodes, then courses (FEEDBACK F4). */
export function RequirementTree({ details, progress, onAddProgram }: RequirementTreeProps) {
  const byNode = progressByNode(progress);
  const ids = details.map((d) => d.id);
  const types = new Map(details.flatMap((d) => (d.data ? [[d.id, d.data.type] as const] : [])));
  return (
    <div className="flex flex-col gap-6">
      {details.length === 0 && <EmptyState>Add a program to see its requirements.</EmptyState>}
      {details.map((d) =>
        d.isLoading ? (
          <Spinner key={d.id} label={`Loading ${d.id}`} />
        ) : d.data ? (
          <ProgramTree key={d.id} program={d.data} kind={stripKind(d.id, ids, types)} progress={byNode} />
        ) : (
          <ErrorText key={d.id}>{isNotAvailable(d.error) ? `Program ${d.id} is not available yet.` : `Could not load program ${d.id}.`}</ErrorText>
        ),
      )}
      <Button variant="outline" onClick={onAddProgram} className="self-start">
        Add program
      </Button>
    </div>
  );
}
