/** Tags of a question: chips with remove buttons, a field (Enter or comma adds, Backspace on an
 * empty field removes the last) and suggestions. At most 5 lowercase slugs. */
import { useId, useState, type KeyboardEvent } from "react";
import { CloseIcon, PlusIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { toTag } from "./text";

export const SUGGESTED_TAGS = [
  "first-year",
  "core",
  "workload",
  "placement",
  "major",
  "minor",
  "humanities",
  "cs",
  "math",
  "econ",
  "pre-med",
  "research",
  "study-abroad",
  "careers",
];
export const MAX_TAGS = 5;

export function TagInput({ value, onChange, suggestions = SUGGESTED_TAGS }: { value: string[]; onChange: (tags: string[]) => void; suggestions?: string[] }) {
  const id = useId();
  const [text, setText] = useState("");
  const full = value.length >= MAX_TAGS;

  function add(raw: string) {
    const tag = toTag(raw);
    if (!tag || value.includes(tag) || full) return;
    onChange([...value, tag]);
    setText("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if ((e.key === "Enter" || e.key === "," || e.key === "Tab") && text.trim()) {
      e.preventDefault();
      add(text);
    } else if (e.key === "Backspace" && !text && value.length) {
      onChange(value.slice(0, -1));
    }
  }

  const left = suggestions.filter((s) => !value.includes(s)).slice(0, 8);
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={`${id}-tag`} className="text-caption font-medium text-ink">
        Tags <span className="font-normal text-muted">(optional, up to {MAX_TAGS})</span>
      </label>
      <div className="flex min-h-[52px] flex-wrap items-center gap-1.5 rounded-[26px] border border-hairline-strong bg-white/[0.04] px-3 py-1.5 focus-within:border-primary focus-within:shadow-[inset_0_0_0_1px_var(--color-primary)]">
        {value.map((tag) => (
          <span key={tag} className="inline-flex items-center gap-0.5 rounded-pill bg-surface-strong pl-2.5 text-caption text-ink">
            #{tag}
            <button type="button" aria-label={`Remove tag ${tag}`} onClick={() => onChange(value.filter((t) => t !== tag))} className="inline-flex size-8 items-center justify-center rounded-pill text-muted hover:bg-hairline hover:text-ink">
              <CloseIcon size={12} />
            </button>
          </span>
        ))}
        <input
          id={`${id}-tag`}
          value={text}
          disabled={full}
          maxLength={30}
          onChange={(e) => (e.target.value.endsWith(",") ? add(e.target.value.slice(0, -1)) : setText(e.target.value))}
          onKeyDown={onKeyDown}
          onBlur={() => text.trim() && add(text)}
          placeholder={full ? "Five tags is the most" : value.length ? "Add another" : "e.g. workload, first-year"}
          aria-describedby={`${id}-hint`}
          className="min-h-9 min-w-32 flex-1 bg-transparent px-1 text-body-sm text-ink placeholder:text-muted focus:outline-none pointer-coarse:text-body-md"
        />
      </div>
      <p id={`${id}-hint`} className="sr-only">
        Press Enter or a comma to add a tag; Backspace removes the last one.
      </p>
      {left.length > 0 && !full && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-caption text-muted">Suggestions:</span>
          {left.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add(s)}
              className={cn("inline-flex min-h-11 items-center gap-1 rounded-pill px-2.5 text-caption text-body hover:bg-surface-strong hover:text-ink")}
            >
              <PlusIcon size={12} />
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
