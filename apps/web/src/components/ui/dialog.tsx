import { useEffect, useId, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { CloseIcon } from "./icons";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal focus handling: on `active`, focus moves to `initial` (or the first focusable element) and
 * Tab is trapped inside `ref`; Escape calls `onEscape`; focus goes back where it was afterwards.
 */
export function useFocusTrap(ref: RefObject<HTMLElement | null>, active: boolean, onEscape: () => void, initial?: RefObject<HTMLElement | null>) {
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;
  useEffect(() => {
    if (!active) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const first = initial?.current ?? node?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? node)?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        // A dialog opened on top (its own trap) handles its own Escape.
        const inside = !!node && (node.contains(document.activeElement) || document.activeElement === document.body);
        if (!inside) return;
        e.stopPropagation();
        onEscapeRef.current();
      } else if (e.key === "Tab" && node) {
        const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)];
        if (items.length === 0) return;
        const firstItem = items[0] as HTMLElement;
        const lastItem = items[items.length - 1] as HTMLElement;
        if (e.shiftKey && document.activeElement === firstItem) {
          e.preventDefault();
          lastItem.focus();
        } else if (!e.shiftKey && document.activeElement === lastItem) {
          e.preventDefault();
          firstItem.focus();
        }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [active, ref, initial]);
}

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

/**
 * Modal dialog: focus moves in on open and back on close, Tab is trapped, Escape closes. The
 * backdrop fades in and the panel fades and scales up (200ms; none under reduced motion).
 */
export function Dialog({ open, onClose, title, description, children, className }: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descId = useId();
  useFocusTrap(ref, open, onClose);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex animate-fade-in items-end justify-center bg-ink/40 p-0 sm:items-center sm:p-4">
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={cn(
          "max-h-[92vh] w-full max-w-lg animate-dialog-in overflow-y-auto rounded-t-xxl border border-hairline bg-surface-card p-5 text-ink shadow-overlay sm:rounded-xl sm:p-6",
          className,
        )}
      >
        <div className="mb-2 flex items-start justify-between gap-3">
          <h2 id={titleId} className="pt-2 font-display text-display-sm">
            {title}
          </h2>
          <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose} className="-mr-2 -mt-1">
            <CloseIcon />
          </Button>
        </div>
        {description ? (
          <p id={descId} className="mb-5 text-body-sm text-muted">
            {description}
          </p>
        ) : (
          <div className="mb-3" />
        )}
        {children}
      </div>
    </div>,
    document.body,
  );
}
