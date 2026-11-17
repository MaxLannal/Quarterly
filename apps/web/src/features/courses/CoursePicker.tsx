import { useDeferredValue, useEffect, useId, useRef, useState } from "react";
import { useCourseSearch } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { controlClass, controlCompactClass } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface CoursePickerProps {
  id: string;
  catalogYear: string;
  /** The chosen course code, or "" for none. */
  value: string;
  onChange: (code: string, title?: string) => void;
  /** Text typed but not chosen yet; the form refuses to save while it is set. */
  onPendingChange?: (text: string) => void;
  /** Smaller text and padding, for dense forms such as the planner's credits drawer. */
  compact?: boolean;
}

/**
 * Pick a course of the catalog by code or name (FEEDBACK "Select Course to map when Start
 * Planning", 2026-11-16): the student may type either, but only a course chosen from the list
 * is accepted, so a credit can never point at a course the catalog does not have.
 */
export function CoursePicker({
  id,
  catalogYear,
  value,
  onChange,
  onPendingChange,
  compact = false,
}: CoursePickerProps) {
  const listId = useId();
  const input = useRef<HTMLInputElement>(null);
  // True while a mouse or touch press is down anywhere on the page (see onBlur).
  const pressing = useRef(false);
  useEffect(() => {
    const down = () => void (pressing.current = true);
    const up = () => window.setTimeout(() => void (pressing.current = false), 0);
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("pointerup", up, true);
    return () => {
      document.removeEventListener("pointerdown", down, true);
      document.removeEventListener("pointerup", up, true);
    };
  }, []);
  const [text, setText] = useState("");
  const [title, setTitle] = useState<string | undefined>(undefined);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const query = useDeferredValue(text.trim());
  const search = useCourseSearch(
    { q: query, catalog_year: catalogYear, limit: 8 },
    query.length >= 2,
  );
  const options = query.length >= 2 ? (search.data?.items ?? []) : [];

  function type(next: string) {
    setText(next);
    setOpen(true);
    setActive(0);
    onPendingChange?.(next.trim());
  }

  function choose(code: string, courseTitle: string) {
    onChange(code, courseTitle);
    setTitle(courseTitle);
    setText("");
    setOpen(false);
    onPendingChange?.("");
  }

  if (value) {
    return (
      <div
        className="flex min-h-11 flex-wrap items-center justify-between gap-2 rounded-md border border-hairline-strong bg-surface-card pl-3 pr-1 text-body-sm text-ink"
        data-testid="course-picked"
      >
        <span>
          <span className="font-medium tabular-nums">{value}</span>
          {title ? <span className="text-muted"> · {title}</span> : null}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={`Change the course (${value})`}
          onClick={() => {
            onChange("");
            setTitle(undefined);
          }}
        >
          Change
        </Button>
      </div>
    );
  }

  const expanded = open && query.length >= 2;
  return (
    <div className="relative">
      <input
        ref={input}
        id={id}
        role="combobox"
        aria-expanded={expanded}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          expanded && options[active] ? `${listId}-${active}` : undefined
        }
        autoComplete="off"
        className={cn(controlClass, compact && controlCompactClass)}
        placeholder={
          compact
            ? "Code or name, then choose"
            : "Type a code or name, then choose"
        }
        value={text}
        onChange={(e) => type(e.target.value)}
        onFocus={() => setOpen(true)}
        // Options keep focus on this field when clicked (mousedown is prevented), so a blur
        // means focus really left. (The close below checks focus first, so it never hides a
        // list that was reopened in the meantime.)
        // The list sits in the page flow (D11 CR-4), so closing it moves what is below. After a press
        // elsewhere, close once that click has landed, so the button being clicked does not jump away;
        // after a keyboard move, close now. Stay open if focus came back to this field.
        onBlur={() => {
          if (!pressing.current) return setOpen(false);
          const close = () => {
            if (document.activeElement !== input.current) setOpen(false);
          };
          document.addEventListener("click", close, { once: true });
          window.setTimeout(close, 500);
        }}
        onKeyDown={(e) => {
          if (!expanded) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, Math.max(options.length - 1, 0)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && options[active]) {
            e.preventDefault();
            choose(options[active].code, options[active].title);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {/* In the page flow, not floating: it pushes the form's buttons down instead of covering them,
          and a drawer's scroll area cannot clip it (D11 CR-4). */}
      {expanded && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Matching courses"
          className="mt-1 max-h-60 w-full overflow-auto rounded-md border border-hairline bg-surface-card py-1"
        >
          {options.length === 0 ? (
            <li className="px-3 py-2 text-body-sm text-muted">
              {search.isFetching
                ? "Searching…"
                : "No course matches. Check the code, or leave this empty."}
            </li>
          ) : (
            options.map((c, i) => (
              <li
                key={c.code}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault(); // keep focus; choose on click
                  choose(c.code, c.title);
                }}
                onMouseEnter={() => setActive(i)}
                className={cn(
                  "flex min-h-11 cursor-pointer items-center gap-2 px-3 text-body-sm text-ink",
                  i === active && "bg-primary-wash",
                )}
              >
                <span className="font-medium tabular-nums">{c.code}</span>
                <span className="truncate text-muted">{c.title}</span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
