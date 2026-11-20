/**
 * The Commons composer: a markdown editor for questions, answers and replies.
 *
 * - Toolbar (bold, italic, code, link, quote, bulleted and numbered lists) with Cmd/Ctrl+B, I, K
 *   and E; the formatting wraps the selection and keeps the browser's undo where it can.
 * - Write / Preview tabs; the preview is a safe React renderer of the server's markdown subset.
 * - Course mentions: typing a subject and digits ("CMSC 1", "math 15") opens a list of real
 *   courses (GET /courses?q=); arrows choose, Enter or Tab insert the canonical code, Esc closes
 *   (the ARIA combobox pattern).
 * - "@quarterly" asks the AI to answer under the reply.
 * - A draft per context in this browser ("Draft saved"), restored on return, cleared on submit.
 * - A character counter near the limit, Cmd/Ctrl+Enter submits, Esc cancels an inline composer
 *   (asking first when there is text), the field grows with its text.
 */
import {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/button";
import { ErrorText } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { useCourseMatches } from "./api";
import { clearDraft, readDraft, writeDraft } from "./drafts";
import { MarkdownPreview } from "./markdown";
import { applyFormat, applyMention, findMention, type FormatKind, type Mention } from "./text";

export interface ComposerHandle {
  focus: () => void;
  clear: () => void;
  value: () => string;
}

export interface ComposerProps {
  label: string;
  labelHidden?: boolean;
  placeholder?: string;
  /** Autosave key (one draft per context); none: no draft. */
  draftKey?: string;
  initialValue?: string;
  maxLength?: number;
  /** Allow posting an empty text (a question's optional details). */
  optional?: boolean;
  rows?: number;
  submitLabel?: string;
  submittingLabel?: string;
  /** Called with the text; resolve on success (the text and draft are cleared), throw to show the error. */
  onSubmit?: (text: string) => Promise<unknown>;
  /** The parent shows its own submit button (Cmd/Ctrl+Enter still calls onSubmit). */
  hideSubmit?: boolean;
  onChange?: (text: string) => void;
  /** Inline composers: Esc or Cancel closes them (asking first when there is text). */
  onCancel?: () => void;
  onTyping?: () => void;
  /** Focus the field when the composer opens (inline reply and edit composers). */
  focusOnMount?: boolean;
  /** Show the "@quarterly asks the AI" hint. */
  summonHint?: boolean;
  disabled?: boolean;
  className?: string;
  /** Extra controls beside the submit button. */
  actions?: ReactNode;
}

const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const MOD = IS_MAC ? "⌘" : "Ctrl+";

const TOOLS: { kind: FormatKind; label: string; key?: string; icon: ReactNode }[] = [
  { kind: "bold", label: "Bold", key: "B", icon: <span className="font-sans text-[15px] font-bold">B</span> },
  { kind: "italic", label: "Italic", key: "I", icon: <span className="font-serif text-[18px] italic">I</span> },
  {
    kind: "code",
    label: "Code",
    key: "E",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m8 7-5 5 5 5M16 7l5 5-5 5" />
      </svg>
    ),
  },
  {
    kind: "link",
    label: "Link",
    key: "K",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1" />
        <path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1" />
      </svg>
    ),
  },
  {
    kind: "quote",
    label: "Quote",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M5 17h4l2-4V7H5v6h3zM13 17h4l2-4V7h-6v6h3z" />
      </svg>
    ),
  },
  {
    kind: "bullets",
    label: "Bulleted list",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <path d="M9 6h11M9 12h11M9 18h11" />
        <circle cx="4.5" cy="6" r="1" fill="currentColor" />
        <circle cx="4.5" cy="12" r="1" fill="currentColor" />
        <circle cx="4.5" cy="18" r="1" fill="currentColor" />
      </svg>
    ),
  },
  {
    kind: "numbers",
    label: "Numbered list",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <path d="M10 6h10M10 12h10M10 18h10" />
        <path d="M4 5h1.5v4M3.5 9h3M3.6 14.2a1.3 1.3 0 0 1 2.4.6c0 1-2.4 1.6-2.4 3.2h2.6" strokeWidth="1.5" />
      </svg>
    ),
  },
];

/** The smallest changed range between two texts (for an undoable insertText). */
function diff(before: string, after: string): { start: number; end: number; insert: string } {
  let start = 0;
  while (start < before.length && start < after.length && before[start] === after[start]) start += 1;
  let endB = before.length;
  let endA = after.length;
  while (endB > start && endA > start && before[endB - 1] === after[endA - 1]) {
    endB -= 1;
    endA -= 1;
  }
  return { start, end: endB, insert: after.slice(start, endA) };
}

const MIRRORED = [
  "boxSizing", "width", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "borderTopWidth",
  "borderRightWidth", "borderBottomWidth", "borderLeftWidth", "fontFamily", "fontSize", "fontWeight",
  "fontStyle", "letterSpacing", "lineHeight", "textTransform", "wordSpacing", "tabSize",
] as const;

/** The caret's position inside a textarea (a hidden mirror element with the same text). */
function caretPoint(el: HTMLTextAreaElement, index: number): { top: number; left: number; height: number } | null {
  if (typeof window === "undefined" || !el.offsetParent) return null;
  const style = window.getComputedStyle(el);
  const mirror = document.createElement("div");
  for (const key of MIRRORED) mirror.style[key] = style[key];
  mirror.style.position = "absolute";
  mirror.style.visibility = "hidden";
  mirror.style.whiteSpace = "pre-wrap";
  mirror.style.overflowWrap = "break-word";
  mirror.style.top = "0";
  mirror.style.left = "-9999px";
  mirror.textContent = el.value.slice(0, index);
  const marker = document.createElement("span");
  marker.textContent = el.value.slice(index, index + 1) || ".";
  mirror.appendChild(marker);
  document.body.appendChild(mirror);
  const top = marker.offsetTop - el.scrollTop + el.offsetTop;
  const left = marker.offsetLeft - el.scrollLeft + el.offsetLeft;
  const height = parseFloat(style.lineHeight) || marker.offsetHeight || 24;
  mirror.remove();
  return { top, left, height };
}

export const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(
  {
    label,
    labelHidden = false,
    placeholder,
    draftKey,
    initialValue = "",
    maxLength = 8000,
    optional = false,
    rows = 4,
    submitLabel = "Post",
    submittingLabel = "Posting…",
    onSubmit,
    hideSubmit = false,
    onChange,
    onCancel,
    onTyping,
    focusOnMount = false,
    summonHint = false,
    disabled = false,
    className,
    actions,
  },
  ref,
) {
  const base = useId();
  const area = useRef<HTMLTextAreaElement>(null);
  const [restored] = useState(() => (draftKey && !initialValue ? readDraft<string>(draftKey) : null));
  const [value, setValueState] = useState(() => restored ?? initialValue);
  const [showRestored, setShowRestored] = useState(!!restored);
  const [tab, setTab] = useState<"write" | "preview">("write");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<"saved" | "failed" | null>(null);
  const [caret, setCaret] = useState(0);
  const [dismissedAt, setDismissedAt] = useState<number | null>(null);
  const [active, setActive] = useState(0);
  const pendingSelection = useRef<[number, number] | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const setValue = useCallback((next: string) => {
    setValueState(next);
    onChangeRef.current?.(next);
  }, []);

  useEffect(() => {
    if (restored) onChangeRef.current?.(restored);
  }, [restored]);

  // Autosave the draft half a second after typing stops.
  useEffect(() => {
    if (!draftKey) return;
    const t = window.setTimeout(() => {
      if (!value.trim() || value === initialValue) {
        clearDraft(draftKey);
        setSavedNote(null);
        return;
      }
      setSavedNote(writeDraft(draftKey, value) ? "saved" : "failed");
    }, 500);
    return () => window.clearTimeout(t);
  }, [draftKey, value, initialValue]);

  // Grow with the text (up to a limit, then scroll inside).
  useLayoutEffect(() => {
    const el = area.current;
    if (!el || tab !== "write") return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight + 2, 520)}px`;
  }, [value, tab]);

  useLayoutEffect(() => {
    const sel = pendingSelection.current;
    const el = area.current;
    if (sel && el) {
      el.setSelectionRange(sel[0], sel[1]);
      pendingSelection.current = null;
      setCaret(sel[1]);
    }
  }, [value, tab]);

  useEffect(() => {
    if (focusOnMount) area.current?.focus();
  }, [focusOnMount]);

  useImperativeHandle(
    ref,
    () => ({
      focus: () => {
        setTab("write");
        window.setTimeout(() => area.current?.focus(), 0);
      },
      clear: () => {
        setValue("");
        if (draftKey) clearDraft(draftKey);
      },
      value: () => value,
    }),
    [draftKey, setValue, value],
  );

  /** Replace the whole text, keeping undo where the browser supports insertText. */
  function edit(next: string, selStart: number, selEnd: number) {
    const el = area.current;
    const change = diff(value, next);
    let done = false;
    if (el && typeof document.execCommand === "function") {
      el.focus();
      el.setSelectionRange(change.start, change.end);
      try {
        done = document.execCommand("insertText", false, change.insert);
      } catch {
        done = false;
      }
    }
    if (!done || (el && el.value !== next)) setValue(next);
    pendingSelection.current = [selStart, selEnd];
    if (done && el) {
      el.setSelectionRange(selStart, selEnd);
      setCaret(selEnd);
    }
  }

  function format(kind: FormatKind) {
    const el = area.current;
    if (!el) return;
    if (tab !== "write") setTab("write");
    const out = applyFormat(value, el.selectionStart, el.selectionEnd, kind);
    edit(out.text, out.selStart, out.selEnd);
  }

  // ------------------------------------------------------------------ course mentions
  const mention: Mention | null = useMemo(
    () => (tab === "write" ? findMention(value, caret) : null),
    [value, caret, tab],
  );
  const matches = useCourseMatches(mention?.query ?? "", 6);
  const options = mention
    ? (matches.data?.items ?? [])
        .filter((c) => c.code.replace(" ", "").startsWith(mention.query.replace(" ", "")))
        .sort((x, y) => x.code.localeCompare(y.code))
    : [];
  const listOpen = !!mention && options.length > 0 && dismissedAt !== mention.start;
  const listId = `${base}-courses`;
  const optionId = (i: number) => `${base}-course-${i}`;

  useEffect(() => setActive(0), [mention?.query]);

  // Where the caret is in the field, so the course list opens right under it.
  const [caretBox, setCaretBox] = useState<{ top: number; left: number } | null>(null);
  useLayoutEffect(() => {
    const el = area.current;
    if (!el || !mention) {
      setCaretBox(null);
      return;
    }
    const at = caretPoint(el, mention.start);
    if (!at) return setCaretBox(null);
    const width = Math.min(352, el.clientWidth - 16);
    setCaretBox({ top: at.top + at.height + 4, left: Math.max(8, Math.min(at.left, el.clientWidth - width - 8)) });
  }, [mention, value]);

  function insertCourse(code: string) {
    if (!mention) return;
    const out = applyMention(value, mention, code);
    edit(out.text, out.caret, out.caret);
    setDismissedAt(null);
  }

  // ------------------------------------------------------------------ submit / cancel
  const length = value.length;
  const tooLong = length > maxLength;
  const empty = !value.trim();
  const dirty = value.trim() !== initialValue.trim();

  async function submit() {
    if (!onSubmit || pending || disabled) return;
    if (tooLong) {
      setError(`That is ${length - maxLength} characters over the limit.`);
      return;
    }
    if (empty && !optional) {
      setError("Write something first.");
      area.current?.focus();
      return;
    }
    setPending(true);
    setError(null);
    try {
      await onSubmit(value);
      setValue("");
      setTab("write");
      setShowRestored(false);
      if (draftKey) clearDraft(draftKey);
      setSavedNote(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setPending(false);
    }
  }

  function cancel() {
    if (!onCancel) return;
    if (dirty && !window.confirm("Discard what you wrote?")) return;
    if (draftKey) clearDraft(draftKey);
    onCancel();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (listOpen) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const step = e.key === "ArrowDown" ? 1 : -1;
        setActive((a) => (a + step + options.length) % options.length);
        return;
      }
      if ((e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey) || e.key === "Tab") {
        const chosen = options[active];
        if (chosen) {
          e.preventDefault();
          insertCourse(chosen.code);
          return;
        }
      }
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setDismissedAt(mention?.start ?? null);
        return;
      }
    }
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key === "Enter") {
      e.preventDefault();
      void submit();
      return;
    }
    if (mod && !e.altKey && !e.shiftKey) {
      const tool = TOOLS.find((t) => t.key && t.key.toLowerCase() === e.key.toLowerCase());
      if (tool) {
        e.preventDefault();
        format(tool.kind);
        return;
      }
    }
    if (e.key === "Escape" && onCancel) {
      e.preventDefault();
      e.stopPropagation();
      cancel();
    }
  }

  function track() {
    const el = area.current;
    if (el) setCaret(el.selectionEnd);
  }

  const hintId = `${base}-hint`;
  const counterId = `${base}-count`;
  const showCount = length >= maxLength * 0.8;

  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={`${base}-text`} className={cn("text-caption font-medium text-ink", labelHidden && "sr-only")}>
        {label}
      </label>
      <div
        className={cn(
          "min-w-0 rounded-lg border border-border-input bg-surface-card transition-colors",
          "focus-within:border-primary focus-within:shadow-[inset_0_0_0_1px_var(--color-primary)]",
          (tooLong || error) && "border-error",
          disabled && "opacity-60",
        )}
      >
        <div className="flex flex-wrap items-center justify-between gap-1 border-b border-hairline px-1">
          <div role="tablist" aria-label={`${label}: write or preview`} className="flex">
            {(["write", "preview"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                id={`${base}-tab-${t}`}
                aria-selected={tab === t}
                aria-controls={`${base}-panel`}
                tabIndex={tab === t ? 0 : -1}
                onClick={() => setTab(t)}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    const next = tab === "write" ? "preview" : "write";
                    setTab(next);
                    document.getElementById(`${base}-tab-${next}`)?.focus();
                  }
                }}
                className={cn(
                  "-mb-px inline-flex min-h-11 items-center border-b-2 px-3 text-caption font-medium transition-colors focus-visible:outline-offset-[-2px]",
                  tab === t ? "border-primary text-ink" : "border-transparent text-muted hover:text-ink",
                )}
              >
                {t === "write" ? "Write" : "Preview"}
              </button>
            ))}
          </div>
          <div role="toolbar" aria-label="Formatting" aria-controls={`${base}-text`} className="flex flex-wrap items-center">
            {TOOLS.map((tool) => (
              <button
                key={tool.kind}
                type="button"
                aria-label={tool.key ? `${tool.label} (${MOD}${tool.key})` : tool.label}
                title={tool.key ? `${tool.label} (${MOD}${tool.key})` : tool.label}
                disabled={disabled || pending}
                onMouseDown={(e) => e.preventDefault() /* keep the selection in the field */}
                onClick={() => format(tool.kind)}
                className="inline-flex size-11 items-center justify-center rounded-md text-body hover:bg-surface-strong hover:text-ink disabled:opacity-40 focus-visible:outline-offset-[-4px]"
              >
                {tool.icon}
              </button>
            ))}
          </div>
        </div>
        <div id={`${base}-panel`} role="tabpanel" aria-labelledby={`${base}-tab-${tab}`} className="relative">
          <textarea
            ref={area}
            id={`${base}-text`}
            value={value}
            rows={rows}
            placeholder={placeholder}
            disabled={disabled || pending}
            hidden={tab !== "write"}
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={listOpen}
            aria-controls={listOpen ? listId : undefined}
            aria-activedescendant={listOpen ? optionId(active) : undefined}
            aria-describedby={`${hintId}${showCount ? ` ${counterId}` : ""}`}
            aria-invalid={tooLong || undefined}
            onChange={(e) => {
              setValue(e.target.value);
              setCaret(e.target.selectionEnd);
              setError(null);
              if (showRestored) setShowRestored(false);
              onTyping?.();
            }}
            onKeyDown={onKeyDown}
            onKeyUp={track}
            onClick={track}
            onSelect={track}
            onBlur={() => window.setTimeout(() => setDismissedAt(mention?.start ?? null), 150)}
            onFocus={() => setDismissedAt(null)}
            className="block min-h-24 w-full resize-none bg-transparent px-4 py-3 font-sans text-body-md text-ink placeholder:text-muted focus:outline-none disabled:cursor-not-allowed pointer-coarse:text-body-md"
          />
          {tab === "preview" && (
            <div className="min-h-24 px-4 py-3">
              <MarkdownPreview source={value} />
            </div>
          )}
          {listOpen && mention && (
            <div
              style={caretBox ? { top: caretBox.top, left: caretBox.left } : undefined}
              className={cn(
                "z-30 w-[min(22rem,calc(100%-1rem))] overflow-hidden rounded-lg border border-hairline bg-surface-card shadow-overlay",
                caretBox ? "absolute" : "relative mx-2 mb-2",
              )}
            >
              <p className="px-4 pt-2 text-caption-uppercase uppercase text-muted">Courses matching “{mention.query}”</p>
              <ul id={listId} role="listbox" aria-label="Matching courses" className="flex flex-col py-1">
                {options.map((c, i) => (
                  <li
                    key={c.code}
                    id={optionId(i)}
                    role="option"
                    aria-selected={i === active}
                    tabIndex={-1}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      insertCourse(c.code);
                    }}
                    onMouseEnter={() => setActive(i)}
                    onKeyDown={() => undefined}
                    className={cn(
                      "flex min-h-11 cursor-pointer items-center gap-3 px-4 text-body-sm",
                      i === active ? "bg-primary-wash text-ink" : "text-body",
                    )}
                  >
                    <span className="shrink-0 font-medium tabular-nums text-primary">{c.code}</span>
                    <span className="min-w-0 truncate">{c.title}</span>
                  </li>
                ))}
              </ul>
              <p className="px-4 pb-2 text-caption text-muted">↑ ↓ to choose · Enter or Tab to insert · Esc to close</p>
            </div>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
          <span id={hintId}>
            Markdown works: **bold**, _italic_, `code`, lists, links. Type a course code to link it
            {summonHint ? (
              <>
                {"; "}
                <span className="font-medium text-primary">@quarterly</span> asks the AI to join
              </>
            ) : null}
            .
          </span>
          <span aria-live="polite" className="min-w-0">
            {showRestored ? (
              <span className="inline-flex items-center gap-1">
                Draft restored.
                <button
                  type="button"
                  className="min-h-11 rounded-xs px-1 text-primary underline underline-offset-2"
                  onClick={() => {
                    setValue(initialValue);
                    setShowRestored(false);
                    if (draftKey) clearDraft(draftKey);
                  }}
                >
                  Discard
                </button>
              </span>
            ) : savedNote === "saved" ? (
              "Draft saved on this device"
            ) : savedNote === "failed" ? (
              "This browser would not save a draft"
            ) : null}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {showCount && (
            <span id={counterId} className={cn("text-caption tabular-nums", tooLong ? "font-medium text-error" : "text-muted")}>
              {length.toLocaleString()} / {maxLength.toLocaleString()}
            </span>
          )}
          {actions}
          {onCancel && (
            <Button type="button" variant="ghost" onClick={cancel} disabled={pending}>
              Cancel
            </Button>
          )}
          {onSubmit && !hideSubmit && (
            <Button type="button" onClick={() => void submit()} disabled={pending || disabled || (empty && !optional) || tooLong} title={`${submitLabel} (${MOD}Enter)`}>
              {pending ? submittingLabel : submitLabel}
            </Button>
          )}
        </div>
      </div>
      {error && (
        <div role="alert">
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  );
});
