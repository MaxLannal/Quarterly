import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface RailTab {
  key: string;
  label: string;
  content: ReactNode;
}

/** WAI-ARIA tabs; panels stay mounted so the advisor conversation survives tab switches. */
export function Tabs({ tabs, label, initial }: { tabs: RailTab[]; label: string; initial?: string }) {
  const [active, setActive] = useState(initial ?? tabs[0]?.key ?? "");
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
    <div>
      <div role="tablist" aria-label={label} className="flex border-b border-border">
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
              "min-h-11 flex-1 border-b-2 px-3 text-sm font-medium",
              active === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tabs.map((t) => (
        <div
          key={t.key}
          role="tabpanel"
          id={`${base}-panel-${t.key}`}
          aria-labelledby={`${base}-tab-${t.key}`}
          hidden={active !== t.key}
          tabIndex={0}
          className="pt-3"
        >
          {t.content}
        </div>
      ))}
    </div>
  );
}
