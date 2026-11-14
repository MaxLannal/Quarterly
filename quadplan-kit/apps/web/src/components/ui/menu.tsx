import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface MenuItem {
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  danger?: boolean;
}

interface MenuProps {
  /** Accessible name of the trigger button, e.g. "Actions for TEST 10000". */
  label: string;
  trigger: ReactNode;
  items: MenuItem[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  className?: string;
}

/**
 * Menu button (WAI-ARIA menu pattern): arrow keys move, Home/End jump, Escape closes and
 * returns focus to the trigger, Tab and outside clicks close.
 */
export function Menu({ label, trigger, items, open, onOpenChange, className }: MenuProps) {
  const id = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    listRef.current?.querySelector<HTMLElement>('[role="menuitem"]:not([disabled])')?.focus();
    function onPointer(e: PointerEvent) {
      const t = e.target as Node;
      if (!listRef.current?.contains(t) && !triggerRef.current?.contains(t)) onOpenChange(false);
    }
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open, onOpenChange]);

  function close(refocus = true) {
    onOpenChange(false);
    if (refocus) triggerRef.current?.focus();
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const nodes = [...(listRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])') ?? [])];
    const idx = nodes.indexOf(document.activeElement as HTMLElement);
    const focus = (i: number) => nodes[(i + nodes.length) % nodes.length]?.focus();
    if (e.key === "ArrowDown") focus(idx + 1);
    else if (e.key === "ArrowUp") focus(idx - 1);
    else if (e.key === "Home") focus(0);
    else if (e.key === "End") focus(nodes.length - 1);
    else if (e.key === "Escape") close();
    else if (e.key === "Tab") close(false);
    else return;
    if (e.key !== "Tab") e.preventDefault();
  }

  return (
    <div className={cn("relative", className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => onOpenChange(!open)}
        className="flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-pill text-muted transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-offset-[-2px] aria-expanded:bg-surface-strong aria-expanded:text-ink"
      >
        {trigger}
      </button>
      {open && (
        <div
          ref={listRef}
          id={id}
          role="menu"
          aria-label={label}
          tabIndex={-1}
          onKeyDown={onKeyDown}
          className="absolute right-0 z-40 mt-1 min-w-52 rounded-lg border border-hairline bg-surface-card p-1 shadow-overlay"
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              tabIndex={-1}
              disabled={item.disabled}
              onClick={() => {
                close(false);
                item.onSelect();
              }}
              className={cn(
                "flex min-h-11 w-full cursor-pointer items-center rounded-sm px-3 text-left text-body-sm text-ink hover:bg-surface-strong focus:bg-primary-wash focus:outline-none disabled:cursor-not-allowed disabled:text-muted-soft disabled:hover:bg-transparent",
                item.danger && "text-error",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
