import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { CloseIcon, PlusIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { errorText, usePatchProfile, type ProfilePatch } from "./api";
import { hasItem, MAX_ITEM_CHARS, MAX_ITEMS, withItem, withoutItem } from "./logic";

export type SaveState = { kind: "idle" } | { kind: "saving" } | { kind: "saved" } | { kind: "error"; message: string };

/** Saves profile patches (optimistically) and keeps a quiet status for one card. */
export function useSaver() {
  const mutation = usePatchProfile();
  const [state, setState] = useState<SaveState>({ kind: "idle" });
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  function save(patch: ProfilePatch, onDone?: () => void) {
    window.clearTimeout(timer.current);
    setState({ kind: "saving" });
    mutation.mutate(patch, {
      onSuccess: () => {
        setState({ kind: "saved" });
        timer.current = window.setTimeout(() => setState({ kind: "idle" }), 2400);
        onDone?.();
      },
      onError: (error) => setState({ kind: "error", message: errorText(error, "Your change") }),
    });
  }
  return { save, state };
}

/** "Saving…" / "Saved" / the error, announced politely. */
export function SaveStatus({ state, className }: { state: SaveState; className?: string }) {
  return (
    <span role="status" aria-live="polite" className={cn("min-h-5 text-caption", state.kind === "error" ? "text-error" : "text-muted", className)}>
      {state.kind === "saving" && "Saving…"}
      {state.kind === "saved" && (
        <span className="inline-flex items-center gap-1">
          <span aria-hidden="true" className="inline-block size-1.5 rounded-pill bg-success" /> Saved
        </span>
      )}
      {state.kind === "error" && state.message}
    </span>
  );
}

/** A dashboard card: a serif title, an optional kicker and status, generous padding. */
export function DashCard({
  id,
  kicker,
  title,
  status,
  actions,
  children,
  className,
  tone = "paper",
}: {
  id?: string;
  kicker?: ReactNode;
  title: ReactNode;
  status?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  tone?: "paper" | "ink" | "soft";
}) {
  const headingId = useId();
  return (
    <section
      id={id}
      aria-labelledby={headingId}
      className={cn(
        "relative min-w-0 scroll-mt-24 rounded-xxl border p-5 sm:p-7",
        tone === "paper" && "border-hairline bg-surface-card",
        tone === "soft" && "border-hairline bg-canvas-soft",
        tone === "ink" && "border-transparent bg-surface-dark text-on-dark",
        className,
      )}
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="min-w-0">
          {kicker && <p className={cn("mb-1 text-caption-uppercase uppercase", tone === "ink" ? "text-on-dark-soft" : "text-primary")}>{kicker}</p>}
          <h2 id={headingId} className={cn("font-display text-display-sm", tone === "ink" ? "text-on-dark" : "text-ink")}>
            {title}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {status}
          {actions}
        </div>
      </div>
      {children}
    </section>
  );
}

/** An empty section's invitation to the guide. */
export function AskGuide({ children, onAsk }: { children: ReactNode; onAsk: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-hairline-strong bg-canvas-soft px-4 py-3">
      <p className="min-w-0 flex-1 text-body-sm text-body">{children}</p>
      <button
        type="button"
        onClick={onAsk}
        className="inline-flex min-h-11 items-center gap-2 rounded-pill px-4 text-button text-primary underline-offset-4 hover:bg-primary-wash hover:underline"
      >
        <GuideMark size={14} /> Ask me about this
      </button>
    </div>
  );
}

/** The guide's mark: a four-pointed star. */
export function GuideMark({ size = 18, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <path d="M12 2.5c.8 5 3.4 7.6 8.5 8.5-5.1.9-7.7 3.5-8.5 8.5-.8-5-3.4-7.6-8.5-8.5 5.1-.9 7.7-3.5 8.5-8.5z" fill="currentColor" />
    </svg>
  );
}

interface ChipFieldProps {
  label: string;
  items: string[];
  onChange: (items: string[], change: { added?: string; removed?: string }) => void;
  placeholder?: string;
  suggestions?: string[];
  /** Render the chips yourself (e.g. a constellation); the field keeps the input and undo. */
  renderItems?: (items: string[], remove: (item: string) => void) => ReactNode;
  tone?: "paper" | "ink";
  className?: string;
}

/**
 * Editable chips: Enter or a comma adds, each chip's × removes (Backspace in the empty input
 * removes the last one), and a removal can be undone for a few seconds.
 */
export function ChipField({ label, items, onChange, placeholder, suggestions = [], renderItems, tone = "paper", className }: ChipFieldProps) {
  const inputId = useId();
  const hintId = useId();
  const [draft, setDraft] = useState("");
  const [undo, setUndo] = useState<{ item: string; index: number } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const undoTimer = useRef<number | undefined>(undefined);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => () => window.clearTimeout(undoTimer.current), []);

  function add(raw: string) {
    const value = raw.replace(/\s+/g, " ").trim().replace(/,$/, "");
    if (!value) return;
    if (value.length > MAX_ITEM_CHARS) {
      setProblem(`Keep each one under ${MAX_ITEM_CHARS} characters.`);
      return;
    }
    if (items.length >= MAX_ITEMS) {
      setProblem(`That's ${MAX_ITEMS}, the most this section holds.`);
      return;
    }
    setProblem(null);
    setDraft("");
    if (hasItem(items, value)) return;
    onChange(withItem(items, value), { added: value });
  }

  function remove(item: string) {
    const index = items.findIndex((i) => i === item);
    onChange(withoutItem(items, item), { removed: item });
    setUndo({ item, index });
    window.clearTimeout(undoTimer.current);
    undoTimer.current = window.setTimeout(() => setUndo(null), 7000);
  }

  function restore() {
    if (!undo) return;
    const next = [...items];
    next.splice(Math.min(undo.index, next.length), 0, undo.item);
    onChange(next, { added: undo.item });
    setUndo(null);
    inputRef.current?.focus();
  }

  const ink = tone === "ink";
  const left = suggestions.filter((s) => !hasItem(items, s)).slice(0, 5);
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {renderItems ? (
        renderItems(items, remove)
      ) : (
        items.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label={label}>
            {items.map((item) => (
              <li key={item}>
                <Chip label={item} onRemove={() => remove(item)} tone={tone} />
              </li>
            ))}
          </ul>
        )
      )}
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={inputId} className="sr-only">
          Add to {label}
        </label>
        <div className={cn("flex min-h-11 min-w-0 flex-1 items-center gap-2 rounded-pill border px-4 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-primary", ink ? "border-on-dark/25 bg-surface-dark-elevated" : "border-hairline-strong bg-surface-card")}>
          <PlusIcon size={14} className={ink ? "text-on-dark-soft" : "text-muted"} />
          <input
            ref={inputRef}
            id={inputId}
            value={draft}
            maxLength={MAX_ITEM_CHARS + 1}
            aria-describedby={hintId}
            placeholder={placeholder ?? "Add one and press Enter"}
            onChange={(e) => {
              const v = e.target.value;
              if (v.endsWith(",")) add(v);
              else setDraft(v);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                add(draft);
              } else if (e.key === "Backspace" && !draft && items.length) {
                remove(items[items.length - 1] as string);
              }
            }}
            onBlur={() => draft.trim() && add(draft)}
            className={cn("min-h-11 min-w-0 flex-1 bg-transparent text-body-sm outline-none", ink ? "text-on-dark placeholder:text-on-dark-soft" : "text-ink placeholder:text-muted")}
          />
        </div>
      </div>
      <p id={hintId} className="sr-only">
        Press Enter or type a comma to add. Backspace in the empty field removes the last one.
      </p>
      {left.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={cn("text-caption", ink ? "text-on-dark-soft" : "text-muted")}>Ideas:</span>
          {left.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add(s)}
              className={cn("min-h-11 rounded-pill border-[6px] border-transparent bg-clip-padding px-3 text-caption", ink ? "bg-surface-dark-elevated text-on-dark hover:bg-on-dark/15" : "bg-surface-strong text-ink hover:bg-hairline")}
            >
              + {s}
            </button>
          ))}
        </div>
      )}
      {problem && <p className="text-caption text-error">{problem}</p>}
      {undo && (
        <p role="status" className={cn("flex items-center gap-2 text-caption", ink ? "text-on-dark-soft" : "text-muted")}>
          Removed “{undo.item}”.
          <button type="button" onClick={restore} className="min-h-11 rounded-pill px-2 font-medium text-primary underline underline-offset-2">
            Undo
          </button>
        </p>
      )}
    </div>
  );
}

export function Chip({ label, onRemove, tone = "paper", className }: { label: string; onRemove?: () => void; tone?: "paper" | "ink"; className?: string }) {
  const ink = tone === "ink";
  return (
    <span className={cn("inline-flex min-h-9 max-w-full items-center gap-1 rounded-pill border pl-3.5 text-body-sm", onRemove ? "pr-0.5" : "pr-3.5", ink ? "border-on-dark/20 bg-surface-dark-elevated text-on-dark" : "border-hairline-strong bg-surface-card text-ink", className)}>
      <span className="truncate">{label}</span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${label}`}
          className={cn("-my-1 inline-flex size-11 shrink-0 items-center justify-center rounded-pill", ink ? "text-on-dark-soft hover:text-on-dark" : "text-muted hover:text-ink")}
        >
          <span className={cn("inline-flex size-6 items-center justify-center rounded-pill", ink ? "hover:bg-on-dark/15" : "hover:bg-surface-strong")}>
            <CloseIcon size={12} />
          </span>
        </button>
      )}
    </span>
  );
}

/** The share of the portrait filled in, as a maroon ring. */
export function CompletenessRing({ value, size = 64 }: { value: number; size?: number }) {
  const r = size / 2 - 5;
  const c = 2 * Math.PI * r;
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="inline-flex items-center gap-3">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Your portrait is ${pct}% complete`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-hairline-strong)" strokeWidth="4" />
        <circle
          className="dash-ring-fill"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-primary)"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text x="50%" y="52%" textAnchor="middle" dominantBaseline="middle" className="fill-ink font-sans text-[13px] font-semibold tabular-nums">
          {pct}%
        </text>
      </svg>
      <span className="max-w-[11rem] text-caption text-body">{pct >= 100 ? "Your portrait is complete. Come back when something changes." : pct === 0 ? "Your portrait is a blank page so far." : "of your portrait is drawn."}</span>
    </div>
  );
}
