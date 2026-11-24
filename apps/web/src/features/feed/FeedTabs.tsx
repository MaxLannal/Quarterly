import { useRef, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";
import type { FeedTab } from "./api";

export const TABS: { key: FeedTab; label: string; hint: string }[] = [
  { key: "for_you", label: "For you", hint: "Ranked by your interests and focus" },
  { key: "explore", label: "Explore", hint: "A daily shuffle, leaning away from your focus" },
  { key: "following", label: "Following", hint: "The courses and threads you follow" },
];

/** For you / Explore / Following (WAI-ARIA tabs controlling the one feed panel). */
export function FeedTabs({ active, onChange, panelId }: { active: FeedTab; onChange: (tab: FeedTab) => void; panelId: string }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function onKey(e: KeyboardEvent, i: number) {
    let next = -1;
    if (e.key === "ArrowRight") next = (i + 1) % TABS.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + TABS.length) % TABS.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = TABS.length - 1;
    if (next < 0) return;
    e.preventDefault();
    onChange(TABS[next]!.key);
    refs.current[next]?.focus();
  }
  return (
    <div role="tablist" aria-label="Feed" className="flex gap-1 overflow-x-auto border-b border-hairline">
      {TABS.map((t, i) => {
        const on = t.key === active;
        return (
          <button
            key={t.key}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`feed-tab-${t.key}`}
            aria-selected={on}
            aria-controls={panelId}
            tabIndex={on ? 0 : -1}
            title={t.hint}
            onClick={() => onChange(t.key)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              "relative -mb-px inline-flex min-h-11 shrink-0 items-center whitespace-nowrap px-4 text-nav-link transition-colors",
              on ? "text-ink after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-pill after:bg-primary" : "text-muted hover:text-ink",
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
