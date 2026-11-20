import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useCourseSearch } from "@/api/hooks";
import { ArrowIcon, SearchIcon, SparkIcon } from "@/components/ui/icons";
import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * The homepage's question bar (docs/BEST-OF-UCHICAGO-PLAN.md): an agent harness, not a search box.
 * Whatever the student types becomes a question for the Ask chatbot (`/ask?q=`), and the bar reads
 * the intent as they type: an exact course code opens that course, a title shows matching courses,
 * and a question can also go to the Commons. It is a combobox: arrows move through the options,
 * Enter takes the highlighted one, Escape closes.
 */

export const ASK_EXAMPLES = [
  "Which Core humanities sequence suits someone who loves film?",
  "How do I get into quantum computing research as a first-year?",
  "What do students say about MATH 15100?",
  "What's the difference between the CS BA and the BS?",
  "Can I study abroad and still double major in Econ?",
  "Where should a future doctor start in the sciences?",
];

const CODE = /^\s*([a-z]{2,5})\s*-?\s*(\d{5})\s*$/i;
const QUESTION =
  /\?\s*$|^(what|how|which|who|when|where|why|is|are|can|could|should|do|does|will|would|any|tips)\b/i;

type Option =
  | { kind: "ask"; id: string; label: string }
  | { kind: "course"; id: string; code: string; title: string }
  | { kind: "catalog"; id: string; label: string }
  | { kind: "forum"; id: string; label: string };

const RESTING = "Ask anything about UChicago";

/** Cycles through example questions in the placeholder, typed out letter by letter. */
function useTypedPlaceholder(active: boolean): string {
  const still = useMemo(() => prefersReducedMotion(), []);
  const [text, setText] = useState("");
  useEffect(() => {
    if (still || !active) return;
    let example = 0;
    let shown = 0;
    let pause = 0;
    const timer = window.setInterval(() => {
      const target = ASK_EXAMPLES[example % ASK_EXAMPLES.length] ?? "";
      if (pause > 0) {
        pause -= 1;
        if (pause === 0) {
          example += 1;
          shown = 0;
        }
        return;
      }
      shown += 1;
      setText(target.slice(0, shown));
      if (shown >= target.length) pause = 45; // ~2.7 s to read it
    }, 60);
    return () => window.clearInterval(timer);
  }, [active, still]);
  return still || !active ? RESTING : text || RESTING;
}

export function AskBar() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [focused, setFocused] = useState(false);
  const [debounced, setDebounced] = useState("");
  const listId = useId();
  const inputId = useId();
  const popRef = useRef<HTMLDivElement>(null);
  const placeholder = useTypedPlaceholder(!focused && q === "");

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(q.trim()), 180);
    return () => window.clearTimeout(t);
  }, [q]);

  // The chapel behind listens for the pointer on the whole section; the options sit over it.
  useEffect(() => {
    const el = popRef.current;
    if (!el) return;
    const stop = (e: Event) => e.stopPropagation();
    el.addEventListener("pointermove", stop);
    el.addEventListener("pointerdown", stop);
    return () => {
      el.removeEventListener("pointermove", stop);
      el.removeEventListener("pointerdown", stop);
    };
  }, []);

  const term = q.trim();
  const searchable = debounced.length >= 2 && debounced.length <= 48;
  const courses = useCourseSearch({ q: debounced, limit: 4 }, searchable);

  const options: Option[] = useMemo(() => {
    if (!term) return [];
    const matches = searchable ? (courses.data?.items ?? []) : [];
    const code = CODE.exec(term);
    const exact = code ? `${code[1]!.toUpperCase()} ${code[2]}` : null;
    const exactHit = exact ? matches.find((c) => c.code === exact) : undefined;
    const out: Option[] = [];
    if (exactHit) out.push({ kind: "course", id: "exact", code: exactHit.code, title: exactHit.title });
    out.push({ kind: "ask", id: "ask", label: term });
    for (const c of matches) {
      if (c.code !== exactHit?.code) out.push({ kind: "course", id: c.code, code: c.code, title: c.title });
    }
    if (!exactHit) out.push({ kind: "catalog", id: "catalog", label: term });
    if (QUESTION.test(term)) out.push({ kind: "forum", id: "forum", label: term });
    return out;
  }, [term, searchable, courses.data]);

  useEffect(() => setActive(0), [term]);

  function go(option: Option | undefined) {
    const text = term || (placeholder === RESTING ? "" : placeholder);
    setOpen(false);
    const bare = CODE.exec(text);
    if ((!option || option.id === "ask") && bare) {
      // A bare course code opens the course, even before the matches have loaded.
      navigate(`/courses/${encodeURIComponent(`${bare[1]!.toUpperCase()} ${bare[2]}`)}`);
    } else if (!option || option.kind === "ask") {
      navigate(text ? `/ask?q=${encodeURIComponent(text)}` : "/ask");
    } else if (option.kind === "course") {
      navigate(`/courses/${encodeURIComponent(option.code)}`);
    } else if (option.kind === "catalog") {
      navigate(`/courses?q=${encodeURIComponent(option.label)}`);
    } else {
      navigate(`/forum/new?title=${encodeURIComponent(option.label)}`);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => (options.length ? (i + 1) % options.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (options.length ? (i - 1 + options.length) % options.length : 0));
    } else if (e.key === "Escape") {
      if (open) {
        e.preventDefault();
        setOpen(false);
      } else setQ("");
    }
  }

  const showList = open && options.length > 0;
  const optionId = (i: number) => `${listId}-opt-${i}`;

  return (
    <div className="relative w-full">
      <form
        role="search"
        aria-label="Ask Quarterly"
        onSubmit={(e) => {
          e.preventDefault();
          go(showList ? options[active] : undefined);
        }}
        className={cn(
          "ask-bar relative flex w-full items-center gap-2 rounded-pill border bg-surface-card p-1.5 pl-4 shadow-hover transition-[border-color,box-shadow] duration-200 sm:pl-5",
          focused
            ? "border-primary shadow-[0_0_0_4px_var(--color-primary-wash)]"
            : "border-hairline-strong",
        )}
      >
        <SparkIcon className="shrink-0 text-primary" aria-hidden="true" />
        <label htmlFor={inputId} className="sr-only">
          Ask Quarterly a question about UChicago
        </label>
        <input
          id={inputId}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList ? optionId(active) : undefined}
          autoComplete="off"
          enterKeyHint="send"
          value={q}
          maxLength={400}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setFocused(true);
            setOpen(true);
          }}
          onBlur={() => {
            setFocused(false);
            // let a click on an option land first
            window.setTimeout(() => setOpen(false), 120);
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className="min-h-11 min-w-0 flex-1 bg-transparent text-body-md text-ink outline-none placeholder:text-muted pointer-coarse:text-body-md"
        />
        <button
          type="submit"
          className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-pill bg-primary px-4 text-button text-on-primary transition-colors hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:px-5"
        >
          Ask
          <ArrowIcon aria-hidden="true" />
        </button>
      </form>
      <div ref={popRef} className="absolute inset-x-0 top-full z-30 pt-2" hidden={!showList}>
        <ul
          id={listId}
          role="listbox"
          aria-label="What to do with your question"
          className="overflow-hidden rounded-lg border border-hairline bg-surface-card py-1.5 shadow-overlay"
        >
          {options.map((option, i) => (
            <li
              key={option.id}
              id={optionId(i)}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault(); // keep focus in the input; the input's keys are the keyboard path
                go(option);
              }}
              onMouseEnter={() => setActive(i)}
              className={cn(
                "flex min-h-11 cursor-pointer items-center gap-3 px-4 py-2 text-body-sm text-body",
                i === active && "bg-primary-wash text-ink",
              )}
            >
              <OptionRow option={option} active={i === active} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function EnterHint({ show }: { show: boolean }) {
  return show ? (
    <kbd className="hidden shrink-0 rounded-xs border border-hairline px-1.5 text-caption text-muted sm:inline">
      Enter
    </kbd>
  ) : null;
}

function OptionRow({ option, active }: { option: Option; active: boolean }) {
  if (option.kind === "ask") {
    return (
      <>
        <SparkIcon className="shrink-0 text-primary" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate">
          <span className="text-ink">Ask Quarterly</span>{" "}
          <span className="text-muted">&ldquo;{option.label}&rdquo;</span>
        </span>
        <EnterHint show={active} />
      </>
    );
  }
  if (option.kind === "course") {
    return (
      <>
        <span className="shrink-0 rounded-pill bg-surface-strong px-2 py-0.5 font-mono text-caption text-ink">
          {option.code}
        </span>
        <span className="min-w-0 flex-1 truncate font-display text-body-md font-semibold text-ink">
          {option.title}
        </span>
        <span className="shrink-0 text-caption text-muted">Course</span>
        <EnterHint show={active} />
      </>
    );
  }
  if (option.kind === "catalog") {
    return (
      <>
        <SearchIcon className="shrink-0 text-muted" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate">
          Search the catalog for <span className="text-ink">&ldquo;{option.label}&rdquo;</span>
        </span>
        <EnterHint show={active} />
      </>
    );
  }
  return (
    <>
      <span
        aria-hidden="true"
        className="w-5 shrink-0 text-center font-display text-title-sm text-primary"
      >
        &para;
      </span>
      <span className="min-w-0 flex-1 truncate">
        Ask it in the <span className="text-ink">Forum</span>: students and the AI answer
      </span>
      <EnterHint show={active} />
    </>
  );
}
