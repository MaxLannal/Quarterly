import { forwardRef, useCallback, useEffect, useId, useImperativeHandle, useRef, useState, type KeyboardEvent } from "react";
import { SendIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { MAX_CHARS } from "./conversations";

export interface ComposerHandle {
  focus: () => void;
  setText: (text: string) => void;
}

/**
 * The question box: an autosizing textarea (Enter sends, Shift+Enter adds a line), a counter
 * near the 4000-character limit, and Send / Stop. `size`: "hero" in the Ask page's title,
 * "dock" pinned under a conversation, "compact" in the companion.
 */
export const Composer = forwardRef<
  ComposerHandle,
  {
    onSend: (text: string) => void;
    onStop?: () => void;
    running?: boolean;
    disabled?: boolean;
    placeholder?: string;
    label?: string;
    size?: "hero" | "dock" | "compact";
    /** Focus the box once it appears (wide screens only: a phone keyboard would cover the page). */
    focusOnMount?: boolean;
    className?: string;
  }
>(function Composer(
  { onSend, onStop, running = false, disabled = false, placeholder = "Ask a question about UChicago", label = "Your question", size = "dock", focusOnMount = false, className },
  ref,
) {
  const [text, setText] = useState("");
  const area = useRef<HTMLTextAreaElement>(null);
  const id = useId();
  const counterId = `${id}-count`;
  const maxHeight = size === "hero" ? 220 : size === "compact" ? 140 : 200;

  const resize = useCallback(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [maxHeight]);

  useEffect(resize, [text, resize]);
  useEffect(() => {
    if (focusOnMount) area.current?.focus({ preventScroll: true });
  }, [focusOnMount]);
  useImperativeHandle(ref, () => ({
    focus: () => area.current?.focus({ preventScroll: true }),
    setText: (t: string) => {
      setText(t.slice(0, MAX_CHARS));
      area.current?.focus();
    },
  }));

  const blocked = running || disabled;
  const submit = () => {
    const value = text.trim();
    if (!value || blocked) return;
    onSend(value);
    setText("");
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };
  const near = text.length > MAX_CHARS - 500;

  return (
    <form
      className={cn(
        "ask-composer group relative flex w-full items-end gap-2 rounded-[26px] border border-hairline-strong bg-surface-card shadow-hover transition-[border-color,box-shadow] duration-200 focus-within:border-primary/60 focus-within:shadow-[0_0_0_4px_color-mix(in_srgb,var(--color-primary)_10%,transparent),var(--shadow-overlay)]",
        size === "hero" ? "p-2 pl-5" : size === "compact" ? "p-1.5 pl-3.5" : "p-2 pl-4",
        className,
      )}
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <textarea
        ref={area}
        id={id}
        rows={1}
        value={text}
        maxLength={MAX_CHARS}
        placeholder={placeholder}
        aria-describedby={near ? counterId : undefined}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        className={cn(
          "min-h-11 flex-1 resize-none bg-transparent py-2.5 text-ink outline-none placeholder:text-muted",
          size === "hero" ? "text-[17px] leading-[1.45] sm:text-title-sm" : size === "compact" ? "text-body-sm" : "text-body-md",
        )}
      />
      {near && (
        <span id={counterId} aria-live="polite" className={cn("mb-3.5 shrink-0 text-caption tabular-nums", text.length >= MAX_CHARS ? "text-error" : "text-muted")}>
          {text.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
        </span>
      )}
      {running && onStop ? (
        <button
          type="button"
          onClick={onStop}
          className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-pill border border-hairline-strong bg-surface-card px-4 text-button text-ink transition-colors hover:bg-surface-strong"
        >
          <span aria-hidden="true" className="inline-block size-2.5 rounded-[2px] bg-ink" />
          Stop
        </button>
      ) : (
        <button
          type="submit"
          disabled={blocked || !text.trim()}
          aria-label="Ask"
          className={cn(
            "inline-flex shrink-0 items-center justify-center gap-2 rounded-pill bg-primary text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.97] disabled:bg-surface-strong disabled:text-muted",
            size === "hero" ? "min-h-12 px-5 text-button" : "size-11",
          )}
        >
          {size === "hero" && <span>Ask</span>}
          <SendIcon size={size === "compact" ? 16 : 18} />
        </button>
      )}
    </form>
  );
});
