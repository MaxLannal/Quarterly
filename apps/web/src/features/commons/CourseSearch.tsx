/** Pick a real course by code or title (GET /courses?q=): the Commons' course filter and the
 * ask form's course field. An ARIA combobox; only a course chosen from the list is accepted. */
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { controlClass } from "@/components/ui/input";
import { CloseIcon, SearchIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { useCourseMatches, type CourseRef } from "./api";
import { coursePath } from "./text";

export function CourseSearch({
  id,
  label,
  labelHidden = false,
  value,
  onChange,
  placeholder = "Course code or title",
  card = false,
  className,
}: {
  id?: string;
  label: string;
  labelHidden?: boolean;
  value: CourseRef | null;
  onChange: (course: CourseRef | null) => void;
  placeholder?: string;
  /** Show the chosen course as a card (the ask form) instead of a chip (the filter bar). */
  card?: boolean;
  className?: string;
}) {
  const auto = useId();
  const inputId = id ?? `${auto}-input`;
  const listId = `${auto}-list`;
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(text), 180);
    return () => window.clearTimeout(t);
  }, [text]);
  const matches = useCourseMatches(debounced, 8);
  const options = debounced.trim().length >= 2 ? (matches.data?.items ?? []) : [];
  const showList = open && options.length > 0;

  function choose(course: CourseRef) {
    onChange({ code: course.code, title: course.title });
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
      const c = options[active];
      if (c) choose(c);
    } else if (e.key === "Escape") {
      if (showList) {
        e.preventDefault();
        setOpen(false);
      }
    }
  }

  if (value) {
    return (
      <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
        <span className={cn("text-caption font-medium text-ink", labelHidden && "sr-only")} id={`${auto}-label`}>
          {label}
        </span>
        {card ? (
          <div className="flex min-w-0 items-start justify-between gap-3 rounded-lg border border-primary/25 bg-primary-wash/60 px-4 py-3">
            <div className="min-w-0">
              <p className="text-caption font-semibold tabular-nums text-primary">{value.code}</p>
              <p className="font-display text-title-md font-normal text-ink">{value.title}</p>
              <Link to={coursePath(value.code)} target="_blank" className="inline-flex min-h-11 items-center text-caption text-primary underline underline-offset-2">
                Open the course page
              </Link>
            </div>
            <button
              type="button"
              aria-label={`Remove ${value.code}`}
              onClick={() => {
                onChange(null);
                window.setTimeout(() => input.current?.focus(), 0);
              }}
              className="inline-flex size-11 shrink-0 items-center justify-center rounded-pill text-muted hover:bg-surface-card hover:text-ink"
            >
              <CloseIcon />
            </button>
          </div>
        ) : (
          <div aria-labelledby={`${auto}-label`} role="group" className="flex min-h-11 min-w-0 items-center justify-between gap-1 rounded-md border border-primary/30 bg-primary-wash pl-3 text-caption text-primary">
            <span className="min-w-0 truncate">
              <span className="font-semibold tabular-nums">{value.code}</span>
              <span className="text-primary/80"> · {value.title}</span>
            </span>
            <button type="button" aria-label={`Clear the course filter (${value.code})`} onClick={() => onChange(null)} className="inline-flex size-11 shrink-0 items-center justify-center rounded-md hover:bg-primary/10">
              <CloseIcon size={14} />
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={cn("relative flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={inputId} className={cn("text-caption font-medium text-ink", labelHidden && "sr-only")}>
        {label}
      </label>
      <div className="relative">
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input
          ref={input}
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
          placeholder={placeholder}
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
      </div>
      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Courses"
          className="absolute inset-x-0 top-full z-30 mt-1 max-h-80 overflow-y-auto rounded-lg border border-hairline bg-surface-card py-1 shadow-overlay"
        >
          {options.map((c, i) => (
            <li
              key={c.code}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              tabIndex={-1}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(c);
              }}
              onKeyDown={() => undefined}
              onMouseEnter={() => setActive(i)}
              className={cn("flex min-h-11 cursor-pointer items-center gap-3 px-3 text-body-sm", i === active ? "bg-primary-wash" : "")}
            >
              <span className="shrink-0 font-semibold tabular-nums text-primary">{c.code}</span>
              <span className="min-w-0 truncate text-body">{c.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
