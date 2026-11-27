/** Pick an instructor by name (GET /instructors?q=): the `/forum` list's instructor filter. An
 * ARIA combobox like the course filter; only an instructor chosen from the list is accepted. */
import { useEffect, useId, useState, type KeyboardEvent } from "react";
import { controlClass } from "@/components/ui/input";
import { CloseIcon, SearchIcon } from "@/components/ui/icons";
import { useInstructors, type InstructorSummary } from "@/features/forum/api";
import { cn } from "@/lib/utils";

export function InstructorSearch({
  value,
  onChange,
  className,
}: {
  value: InstructorSummary | null;
  onChange: (instructor: InstructorSummary | null) => void;
  className?: string;
}) {
  const auto = useId();
  const inputId = `${auto}-input`;
  const listId = `${auto}-list`;
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(text.trim()), 180);
    return () => window.clearTimeout(t);
  }, [text]);
  const matches = useInstructors(debounced);
  const options = debounced.length >= 2 ? (matches.data?.items ?? []).slice(0, 8) : [];
  const showList = open && options.length > 0;

  function choose(instructor: InstructorSummary) {
    onChange(instructor);
    setText("");
    setOpen(false);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      if (options.length) setActive((a) => (a + (e.key === "ArrowDown" ? 1 : -1) + options.length) % options.length);
    } else if (e.key === "Enter" && showList) {
      e.preventDefault();
      const i = options[active];
      if (i) choose(i);
    } else if (e.key === "Escape" && showList) {
      e.preventDefault();
      setOpen(false);
    }
  }

  if (value) {
    return (
      <div role="group" aria-label="Instructor filter" className={cn("flex min-h-11 min-w-0 items-center justify-between gap-1 rounded-md border border-primary/30 bg-primary-wash pl-3 text-caption text-primary", className)}>
        <span className="min-w-0 truncate font-semibold">{value.display_name}</span>
        <button
          type="button"
          aria-label={`Clear the instructor filter (${value.display_name})`}
          onClick={() => onChange(null)}
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-md hover:bg-primary/10"
        >
          <CloseIcon size={14} />
        </button>
      </div>
    );
  }

  return (
    <div className={cn("relative min-w-0", className)}>
      <label htmlFor={inputId} className="sr-only">
        Filter by instructor
      </label>
      <SearchIcon className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={showList ? listId : undefined}
        aria-activedescendant={showList ? `${listId}-${active}` : undefined}
        autoComplete="off"
        spellCheck={false}
        value={text}
        placeholder="Filter by instructor"
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={onKeyDown}
        className={cn(controlClass, "pl-9 text-body-sm pointer-coarse:text-body-md")}
      />
      {showList && (
        <ul id={listId} role="listbox" aria-label="Instructors" className="glass-raised absolute inset-x-0 top-full z-30 mt-2 max-h-80 overflow-y-auto rounded-[20px] py-1 shadow-overlay">
          {options.map((i, n) => (
            <li
              key={i.slug}
              id={`${listId}-${n}`}
              role="option"
              aria-selected={n === active}
              tabIndex={-1}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(i);
              }}
              onKeyDown={() => undefined}
              onMouseEnter={() => setActive(n)}
              className={cn("flex min-h-11 cursor-pointer items-center gap-3 px-3 text-body-sm", n === active ? "bg-primary-wash" : "")}
            >
              <span className="min-w-0 truncate font-semibold text-ink">{i.display_name}</span>
              {i.department && <span className="min-w-0 truncate text-caption text-muted">{i.department}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
