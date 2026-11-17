import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useFocusTrap } from "@/components/ui/dialog";
import { CloseIcon } from "@/components/ui/icons";
import { Tabs, type RailTab } from "@/components/ui/tabs";
import { usePresence } from "@/lib/motion";
import { cn } from "@/lib/utils";

export type DrawerTab = "requirements" | "goals" | "credits" | "issues";

export const DRAWER_ID = "plan-panel";

interface PlanDrawerProps {
  open: boolean;
  tab: DrawerTab;
  onTab: (tab: DrawerTab) => void;
  onClose: () => void;
  tabs: (RailTab & { key: DrawerTab })[];
  /** True below the desktop breakpoint, where the drawer covers the whole screen. */
  fullScreen: boolean;
}

/**
 * The planner's right-hand panel (FEEDBACK F4): Requirements, Goals and the plan check, opened
 * from the toolbar. On a desktop it sits beside the grid without covering it and without
 * blocking it, so courses drag from the requirement tree onto the grid. On a phone it is a full
 * screen panel that takes focus and closes with Escape or its Close button. It slides in from the
 * right (250ms; none under reduced motion) and stays mounted while closed, so open requirement
 * nodes and half-filled goal fields survive.
 */
export function PlanDrawer({ open, tab, onTab, onClose, tabs, fullScreen }: PlanDrawerProps) {
  const ref = useRef<HTMLElement>(null);
  const selectedTab = useRef<HTMLElement | null>(null);
  const presence = usePresence(open);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const desktop = open && !fullScreen;

  // Runs before the focus effects below: the tab to focus once the drawer is open.
  useEffect(() => {
    selectedTab.current = ref.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]') ?? null;
  });

  // Phone: a modal panel (focus trapped, Escape closes, focus returns to the toolbar).
  useFocusTrap(ref, open && fullScreen, onClose, selectedTab);

  // Desktop: not modal. Opening moves focus to the current tab and closing returns it, and
  // Escape closes the drawer while focus is inside it.
  useEffect(() => {
    if (!desktop) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    selectedTab.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && node?.contains(document.activeElement)) {
        e.stopPropagation();
        onCloseRef.current();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (node?.contains(document.activeElement) || document.activeElement === document.body) previous?.focus?.();
    };
  }, [desktop]);

  return (
    <section
      ref={ref}
      id={DRAWER_ID}
      aria-label="Plan panel"
      hidden={presence === "closed"}
      data-state={presence}
      data-testid="plan-drawer"
      className={cn(
        "flex flex-col bg-surface-card",
        // Phone and tablet: a full-screen panel over the page.
        "fixed inset-0 z-40",
        // Desktop: a sticky column beside the grid.
        "lg:sticky lg:inset-auto lg:top-4 lg:z-auto lg:h-[calc(100vh-2rem)] lg:w-[380px] lg:shrink-0 lg:rounded-xl lg:border lg:border-hairline lg:shadow-overlay xl:w-[400px]",
        presence === "closing" ? "animate-drawer-out" : "animate-drawer-in",
      )}
      {...(fullScreen ? { role: "dialog", "aria-modal": true } : {})}
    >
      <Tabs
        label="Plan panel"
        tabs={tabs}
        active={tab}
        onChange={(k) => onTab(k as DrawerTab)}
        className="flex min-h-0 flex-1 flex-col"
        panelClassName="min-h-0 flex-1 overflow-y-auto px-4 pb-6 pt-4"
        end={
          <Button variant="ghost" size="icon" aria-label="Close panel" onClick={onClose} className="mr-1 shrink-0">
            <CloseIcon />
          </Button>
        }
      />
    </section>
  );
}

/** Toolbar button that opens the drawer at one tab (and closes it when that tab is showing). */
export function DrawerButton({ active, open, onClick, children }: { active: boolean; open: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <Button
      variant="outline"
      aria-controls={DRAWER_ID}
      aria-expanded={open && active}
      onClick={onClick}
      className={cn(open && active && "bg-primary-wash shadow-[inset_0_0_0_1px_var(--color-primary)] hover:bg-primary-wash")}
    >
      {children}
    </Button>
  );
}
