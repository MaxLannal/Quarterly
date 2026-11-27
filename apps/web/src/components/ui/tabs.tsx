import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface RailTab {
  key: string;
  label: ReactNode;
  content: ReactNode;
}

interface TabsProps {
  tabs: RailTab[];
  label: string;
  initial?: string;
  /** Controlled mode: the current tab and its setter. */
  active?: string;
  onChange?: (key: string) => void;
  /** Shown at the end of the tab row (for example a close button). */
  end?: ReactNode;
  className?: string;
  panelClassName?: string;
}

/** WAI-ARIA tabs. Current tab: ink text over a 2px maroon underline (DESIGN.md active state); panels stay mounted so their state survives tab switches. */
export function Tabs({ tabs, label, initial, active: controlled, onChange, end, className, panelClassName }: TabsProps) {
  const [own, setOwn] = useState(initial ?? tabs[0]?.key ?? "");
  const active = controlled ?? own;
  const setActive = (key: string) => {
    setOwn(key);
    onChange?.(key);
  };
  const base = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKey(e: KeyboardEvent, i: number) {
    let next = -1;
    if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    e.preventDefault();
    const tab = tabs[next];
    if (tab) setActive(tab.key);
    refs.current[next]?.focus();
  }

  return (
    <div className={className}>
      {/* A glass track; the current tab is a lit pill of glass in it (docs/DESIGN.md "Dark glass"). */}
      <div className="flex items-center gap-2">
        <div
          role="tablist"
          aria-label={label}
          className="flex min-w-0 flex-1 gap-1 rounded-pill bg-white/[0.035] p-1 shadow-[inset_0_0_0_1px_var(--color-hairline),inset_0_1px_3px_rgb(0_0_0/0.35)]"
        >
          {tabs.map((t, i) => (
            <button
              key={t.key}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              role="tab"
              id={`${base}-tab-${t.key}`}
              aria-selected={active === t.key}
              aria-controls={`${base}-panel-${t.key}`}
              tabIndex={active === t.key ? 0 : -1}
              onClick={() => setActive(t.key)}
              onKeyDown={(e) => onKey(e, i)}
              className={cn(
                // Phones: 14px and tighter padding, so four tabs and a close button fit 390px (D11 polish).
                "inline-flex min-h-11 flex-1 cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-pill px-1.5 text-caption font-medium transition-[color,background-color,box-shadow] duration-300 focus-visible:outline-offset-[-2px] sm:px-3 sm:text-nav-link",
                active === t.key
                  ? "bg-white/[0.09] text-ink shadow-[inset_0_0_0_1px_rgb(255_255_255/0.12),inset_0_1px_0_rgb(255_255_255/0.14),0_6px_18px_rgb(0_0_0/0.35)]"
                  : "text-muted hover:bg-white/[0.04] hover:text-ink",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        {end}
      </div>
      {tabs.map((t) => (
        <div
          key={t.key}
          role="tabpanel"
          id={`${base}-panel-${t.key}`}
          aria-labelledby={`${base}-tab-${t.key}`}
          hidden={active !== t.key}
          tabIndex={0}
          className={cn("pt-4 focus-visible:outline-offset-4", panelClassName)}
        >
          {t.content}
        </div>
      ))}
    </div>
  );
}
