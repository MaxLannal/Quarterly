import { useDraggable } from "@dnd-kit/core";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { PlanItem } from "@/api/types";
import { Menu, type MenuItem } from "@/components/ui/menu";
import { Dots } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { issuesForItem, REQUIREMENT_COLORS, usePlanner } from "./context";
import { attribute, isEstimate, itemUnits, round1 } from "./metrics";
import { itemLabel, removeItemOps, setCompletedOps, toggleLockOps } from "./planModel";

export function CourseCard({ item }: { item: PlanItem }) {
  const { courses, tags, issues, highlight, edit, openMoveTo } = usePlanner();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const id = item.id ?? `${item.course}-${item.term}`;
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id,
    data: { kind: "item", itemId: item.id },
    disabled: item.locked,
  });

  const course = item.course ? courses.get(item.course) : undefined;
  const tag = item.course ? tags.get(item.course) : undefined;
  const mine = issuesForItem(issues, item);
  const worst = mine.some((i) => i.level === "error") ? "error" : mine.some((i) => i.level === "warning") ? "warning" : null;
  const hours = attribute(course, "workload_hours");
  const difficulty = attribute(course, "difficulty");
  const units = itemUnits(item, course);
  const label = itemLabel(item);
  const isSlot = !item.course;
  const completed = item.status === "completed";

  const items: MenuItem[] = [
    { label: "Move to…", onSelect: () => openMoveTo(item), disabled: item.locked },
    { label: item.locked ? "Unlock" : "Lock", onSelect: () => edit(toggleLockOps(item)) },
    ...(isSlot
      ? []
      : [
          { label: completed ? "Mark as planned" : "Mark completed", onSelect: () => edit(setCompletedOps(item, !completed)) },
          { label: "View course page", onSelect: () => navigate(`/courses/${encodeURIComponent(item.course ?? "")}`) },
        ]),
    { label: "Remove", onSelect: () => edit(removeItemOps(item)), disabled: item.locked, danger: true },
  ];

  return (
    <li
      ref={setNodeRef}
      data-testid="course-card"
      data-course={item.course ?? undefined}
      data-term={item.term}
      data-highlighted={item.id && highlight.items.has(item.id) ? "true" : undefined}
      onContextMenu={(e) => {
        e.preventDefault();
        setMenuOpen(true);
      }}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined}
      className={cn(
        "relative flex items-stretch rounded-md border border-l-4 bg-background text-sm shadow-sm",
        isSlot ? "border-dashed border-zinc-400 border-l-zinc-400" : tag ? REQUIREMENT_COLORS[tag.color % REQUIREMENT_COLORS.length] : "border-l-zinc-300",
        completed && "bg-zinc-50",
        worst === "error" && "border-red-700",
        worst === "warning" && "border-amber-600",
        item.id && highlight.items.has(item.id) && "ring-4 ring-blue-600",
        isDragging && "z-30 opacity-80 shadow-lg",
      )}
    >
      <button
        type="button"
        aria-label={item.locked ? `${label} is locked` : `Drag ${label}`}
        className={cn(
          "flex min-h-11 w-8 shrink-0 touch-none items-center justify-center text-muted-foreground",
          item.locked ? "cursor-not-allowed" : "cursor-grab",
        )}
        {...attributes}
        {...listeners}
      >
        <span aria-hidden="true">{item.locked ? "🔒" : "⠿"}</span>
      </button>
      <div className="min-w-0 flex-1 py-1.5 pr-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-semibold">{isSlot ? "Requirement slot" : item.course}</span>
          {units != null && <span className="text-xs text-muted-foreground">{units} units</span>}
          {completed && <span className="text-xs font-medium text-green-800">Completed</span>}
        </div>
        <div className="truncate text-xs" title={course?.title ?? item.slot_ref ?? undefined}>
          {isSlot ? item.slot_ref : (course?.title ?? "")}
        </div>
        {tag && <div className="truncate text-xs text-muted-foreground">{tag.label}</div>}
        {(hours || difficulty) && (
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
            {hours && (
              <span>
                {isEstimate(hours) ? "~" : ""}
                {round1(hours.value)} h/wk
                {isEstimate(hours) && <span className="sr-only"> (estimate)</span>}
              </span>
            )}
            {difficulty && <Dots value={difficulty.value} label="Difficulty" />}
          </div>
        )}
        {mine.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {mine.map((i, n) => (
              <li key={n} className={cn("text-xs", i.level === "error" ? "text-red-800" : "text-amber-900")}>
                <span aria-hidden="true">{i.level === "error" ? "⛔ " : "⚠ "}</span>
                <span className="sr-only">{i.level}: </span>
                {i.message}
              </li>
            ))}
          </ul>
        )}
      </div>
      <Menu label={`Actions for ${label}`} trigger={<span aria-hidden="true">⋯</span>} items={items} open={menuOpen} onOpenChange={setMenuOpen} />
    </li>
  );
}
