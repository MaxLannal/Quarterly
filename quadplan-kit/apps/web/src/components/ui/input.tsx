import * as React from "react";
import { cn } from "@/lib/utils";
import { ErrorIcon } from "./icons";

/**
 * text-input: white, 8px radius, 44px tall, 12x16px padding, 1px border-input line; on focus the
 * line becomes 2px maroon (drawn as border + 1px inset shadow so the text does not shift).
 * Errors: error-colored line + icon + message below (see Field).
 */
export const controlClass = cn(
  "min-h-11 w-full min-w-0 rounded-md border border-border-input bg-surface-card px-4 py-[9px] font-sans text-body-md text-ink",
  "placeholder:text-muted transition-colors",
  "focus-visible:outline-none focus:border-primary focus:shadow-[inset_0_0_0_1px_var(--color-primary)]",
  "disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted",
  "aria-[invalid=true]:border-error",
);

/** Compact controls for dense panels (planner rails, dialogs): same 44px height, 15px text. */
export const controlCompactClass = "px-3 text-body-sm";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { compact?: boolean }>(
  ({ className, compact, ...props }, ref) => <input ref={ref} className={cn(controlClass, compact && controlCompactClass, className)} {...props} />,
);
Input.displayName = "Input";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement> & { compact?: boolean }>(
  ({ className, compact, ...props }, ref) => (
    <select ref={ref} className={cn(controlClass, "cursor-pointer pr-2", compact && controlCompactClass, className)} {...props} />
  ),
);
Select.displayName = "Select";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => <textarea ref={ref} className={cn(controlClass, "py-3", className)} {...props} />,
);
Textarea.displayName = "Textarea";

/** A form label: Inter 500 at caption size, ink. */
export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  // eslint-disable-next-line jsx-a11y/label-has-associated-control -- callers pass htmlFor or wrap the control
  return <label className={cn("text-caption font-medium text-ink", className)} {...props} />;
}

/** Hint under a control (muted caption). */
export function FieldHint({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <p id={id} className="text-caption text-muted">
      {children}
    </p>
  );
}

/** Error under a control: icon + message, announced. */
export function FieldError({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <p id={id} role="alert" className="flex items-start gap-2 text-caption font-medium text-error">
      <ErrorIcon size={14} className="mt-[3px] shrink-0" />
      <span>{children}</span>
    </p>
  );
}

/** A labelled control stack: label, control, hint. */
export function Field({ label, htmlFor, children, className }: { label: React.ReactNode; htmlFor: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}

/** A checkbox or radio with its label, the whole row a 44px target. */
export function ChoiceRow({ children, className, ...input }: React.InputHTMLAttributes<HTMLInputElement> & { children: React.ReactNode }) {
  return (
    <label className={cn("flex min-h-11 cursor-pointer items-center gap-3 rounded-md text-body-sm text-ink", className)}>
      <input className="size-5 shrink-0 cursor-pointer" {...input} />
      <span className="min-w-0">{children}</span>
    </label>
  );
}
