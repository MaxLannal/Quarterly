import { useId, useState } from "react";
import { CheckIcon } from "@/components/ui/icons";
import { useMediaQuery } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { FeedCategory } from "./api";

export type FocusStatus = "idle" | "saving" | "saved" | "local" | "pending";

const STATUS: Record<FocusStatus, string> = {
  idle: "",
  saving: "Saving to your profile…",
  saved: "Saved to your profile.",
  local: "Kept in this browser.",
  pending: "Kept in this browser; we will save it to your profile when we can.",
};

/** "Your focus": the categories the feed sticks to (multi-select toggle buttons). */
export function FocusChips({
  categories,
  selected,
  onChange,
  status,
}: {
  categories: FeedCategory[] | undefined;
  selected: string[];
  onChange: (keys: string[]) => void;
  status: FocusStatus;
}) {
  const labelId = useId();
  const phone = useMediaQuery("(max-width: 639px)");
  const [expanded, setExpanded] = useState(false);
  const list = categories ?? [];
  const fold = phone ? 5 : 8;
  // Chosen categories always show, even when the list is folded.
  const shown = expanded ? list : list.filter((c, i) => i < fold || selected.includes(c.key));
  const toggle = (key: string) =>
    onChange(selected.includes(key) ? selected.filter((k) => k !== key) : [...list.map((c) => c.key).filter((k) => k === key || selected.includes(k))]);

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-hairline bg-surface-card/85 p-4 backdrop-blur-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p id={labelId} className="text-caption-uppercase uppercase text-ink">
          Your focus
        </p>
        <p className="text-caption text-muted">
          {selected.length === 0 ? "Everything, for now. Pick what you want more of." : `${selected.length} chosen`}
        </p>
      </div>
      <div role="group" aria-labelledby={labelId} className="-m-[5px] flex flex-wrap">
        {categories === undefined &&
          Array.from({ length: 8 }, (_, i) => <span key={i} aria-hidden="true" className="feed-skeleton skeleton h-9 w-28 rounded-pill" />)}
        {shown.map((c) => {
          const on = selected.includes(c.key);
          return (
            <button
              key={c.key}
              type="button"
              aria-pressed={on}
              title={c.blurb}
              onClick={() => toggle(c.key)}
              className={cn(
                "inline-flex min-h-11 items-center gap-1.5 rounded-pill border-[5px] border-transparent bg-clip-padding px-3 text-caption font-medium transition-colors focus-visible:outline-offset-[-3px]",
                on
                  ? "bg-primary text-on-primary hover:bg-primary-hover"
                  : "bg-surface-strong text-ink shadow-[inset_0_0_0_1px_var(--color-hairline)] hover:bg-primary-wash hover:text-primary",
              )}
            >
              {on && <CheckIcon size={13} />}
              {c.label}
            </button>
          );
        })}
        {list.length > fold && (
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex min-h-11 items-center rounded-pill px-3 text-caption font-medium text-primary underline underline-offset-2"
          >
            {expanded ? "Fewer categories" : `All ${list.length} categories`}
          </button>
        )}
      </div>
      <div className="flex min-h-5 flex-wrap items-center justify-between gap-2">
        <p role="status" aria-live="polite" className="text-caption text-muted">
          {STATUS[status]}
        </p>
        {selected.length > 0 && (
          <button type="button" onClick={() => onChange([])} className="inline-flex min-h-11 items-center px-1 text-caption font-medium text-primary underline underline-offset-2">
            Clear focus
          </button>
        )}
      </div>
    </div>
  );
}
