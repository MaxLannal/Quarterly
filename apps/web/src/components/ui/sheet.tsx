import { useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { usePresence } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { useFocusTrap } from "./dialog";

interface TopSheetProps {
  open: boolean;
  onClose: () => void;
  /** Id of the element that names the sheet (its heading). */
  labelledBy: string;
  describedBy?: string;
  /** Element to focus on open (defaults to the first focusable one). */
  initialFocus?: RefObject<HTMLElement | null>;
  children: ReactNode;
  className?: string;
}

/**
 * A modal sheet that slides down from the top (250ms in, 200ms out; instant under reduced
 * motion). Full screen on a phone. Unlike `Dialog` it stays mounted while closed (hidden), so
 * what is inside it, such as a conversation, survives closing and reopening.
 */
export function TopSheet({ open, onClose, labelledBy, describedBy, initialFocus, children, className }: TopSheetProps) {
  const ref = useRef<HTMLDivElement>(null);
  const presence = usePresence(open);
  useFocusTrap(ref, open, onClose, initialFocus);
  const closing = presence === "closing";
  return createPortal(
    // The backdrop is the container itself; a click on it (not on the sheet) closes the sheet.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- Escape and the Close button are the keyboard path
    <div
      hidden={presence === "closed"}
      data-state={presence}
      onClick={(e) => e.target === e.currentTarget && onClose()}
      className={cn(
        "fixed inset-0 z-50 flex justify-center transition-colors duration-200 sm:p-4 sm:pt-0",
        closing ? "bg-transparent" : "animate-fade-in bg-scrim",
      )}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        data-testid="top-sheet"
        className={cn(
          "relative flex h-full w-full max-w-3xl flex-col overflow-hidden bg-surface-card text-ink shadow-overlay sm:h-[min(88vh,820px)] sm:rounded-b-xxl sm:border sm:border-t-0 sm:border-hairline",
          closing ? "animate-sheet-out" : "animate-sheet-in",
          className,
        )}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
