import { useDraggable } from "@dnd-kit/core";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { PlanItem } from "@/api/types";
import { Menu, type MenuItem } from "@/components/ui/menu";
import { ErrorIcon, GripIcon, LockIcon, MoreIcon, WarningIcon } from "@/components/ui/icons";
import { Badge, Dots } from "@/components/ui/misc";
import { inlineLinkClass } from "@/components/layout/page";
import { cn } from "@/lib/utils";
import { issuesForItem, STRIP_CLASSES, usePlanner } from "./context";
import { attribute, isEstimate, itemUnits, round1 } from "./metrics";
import { summarizeIssue } from "./issueText";
import { itemLabel, removeItemOps, setCompletedOps, toggleLockOps } from "./planModel";

export function CourseCard({ item }: { item: PlanItem }) {
  const { courses, tags, issues, highlight, edit, openMoveTo } = usePlanner();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const id = item.id ?? `${item.course}-${item.term}`;
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id,
    data: { kind: "item", itemId: item.id },
    disabled: item.locked,
  });

  const course = item.course ? courses.get(item.course) : undefined;
  const tag = item.course ? tags.get(item.course) : undefined;
  const mine = issuesForItem(issues, item);
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
      data-kind={isSlot ? undefined : (tag?.kind ?? "none")}
      data-highlighted={item.id && highlight.items.has(item.id) ? "true" : undefined}
      onContextMenu={(e) => {
        e.preventDefault();
        setMenuOpen(true);
      }}
      className={cn(
        // A file in its quarter's folder (docs/DESIGN.md "Dark border border-hairline bg-canvas": `.glass-file`, planner.css).
        // The coloured left edge is the requirement strip (FEEDBACK "Color strip", 2026-11-16).
        // The card settles into place when it mounts: on load, and after a drop into a new quarter.
        "glass-file planner-file relative flex animate-settle flex-col border-l-[3px] text-caption text-ink",
        isSlot ? "planner-file-slot border-l-hairline-strong" : STRIP_CLASSES[tag?.kind ?? "none"],
        completed && "planner-file-done",
        // While dragging, the drag overlay follows the pointer; the card stays as a faint placeholder.
        isDragging && "opacity-40",
        // Each card is its own layer, so a card further down would paint over this card's open
        // menu: lift the card while it is open (FEEDBACK "Minor issues", 2026-11-16).
        menuOpen && "z-30",
      )}
    >
      {/* Header row: drag handle, code and units, actions menu (each control a 44px target).
          The body below uses the card's full width, so titles and issue messages are not
          squeezed between the two controls in a narrow quarter column. */}
      <div className="flex items-center">
        <button
          type="button"
          aria-label={item.locked ? `${label} is locked` : `Drag ${label}`}
          className={cn(
            "flex size-11 shrink-0 touch-none items-center justify-center rounded-tl-[10px] text-gray-dark transition-colors hover:text-ink focus-visible:outline-offset-[-2px]",
            item.locked ? "cursor-not-allowed" : "cursor-grab",
          )}
          {...attributes}
          {...listeners}
        >
          {item.locked ? <LockIcon size={14} /> : <GripIcon size={14} />}
        </button>
        <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2 py-1">
          <span className="font-mono text-[13px] font-semibold tabular-nums text-ink">{isSlot ? "Requirement slot" : item.course}</span>
          {units != null && <span className="font-mono text-[12px] tabular-nums text-muted">{units} units</span>}
          {completed && (
            <Badge tone="success" casing="normal" className="px-2 py-0">
              Completed
            </Badge>
          )}
        </div>
        <Menu label={`Actions for ${label}`} trigger={<MoreIcon />} items={items} open={menuOpen} onOpenChange={setMenuOpen} />
      </div>
      <div className="min-w-0 px-3.5 pb-3">
        <div className="truncate text-body-sm font-medium text-ink" title={course?.title ?? item.slot_ref ?? undefined}>
          {isSlot ? item.slot_ref : (course?.title ?? "")}
        </div>
        {tag && <div className="truncate text-muted">{tag.label}</div>}
        {(hours || difficulty) && (
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 tabular-nums text-muted">
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
          <ul className="mt-2 space-y-1 border-t border-hairline pt-2">
            {mine.map((i, n) => {
              // Short form on the card; the full message is in the plan check (FEEDBACK 2026-11-16).
              const short = summarizeIssue(i);
              return (
                <li key={n} className="flex items-start gap-1.5 text-body" title={i.message}>
                  {i.level === "error" ? <ErrorIcon size={14} className="mt-[3px] shrink-0 text-error" /> : <WarningIcon size={14} className="mt-[3px] shrink-0 text-warning-icon" />}
                  <span>
                    <span className="sr-only">{i.level}: </span>
                    {short.card}
                    {short.link && (
                      <>
                        {" "}
                        <Link to={short.link.href} className={inlineLinkClass}>
                          {short.link.label}
                        </Link>
                      </>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </li>
  );
}
