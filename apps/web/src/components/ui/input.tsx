import * as React from "react";
import { cn } from "@/lib/utils";
import { ErrorIcon } from "./icons";

/**
 * text-input: white, 8px radius, 44px tall, 12x16px padding, 1px border-input line; on focus the
 * line becomes 2px maroon (drawn as border + 1px inset shadow so the text does not shift).
 * Errors: error-colored line + icon + message below (see Field).
 */
export const controlClass = cn(
  // Redesign 2026-11-20: pills like the reference's Email and Password fields (26px radius: a
  // pill on one line, a soft rounded box when taller), 52px tall, a soft maroon halo on focus.
  "min-h-[52px] w-full min-w-0 rounded-[26px] border border-hairline-strong bg-white/[0.04] px-5 py-3 font-sans text-body-md text-ink shadow-[inset_0_1px_2px_rgb(0_0_0/0.3)]",
  "placeholder:text-muted transition-[border-color,box-shadow]",
  "hover:border-white/30 focus-visible:outline-none focus:border-primary focus:bg-white/[0.06] focus:shadow-[0_0_0_4px_rgb(255_92_112/0.16),0_0_28px_rgb(255_92_112/0.18)]",
  "disabled:cursor-not-allowed disabled:bg-white/[0.02] disabled:text-muted",
  "aria-[invalid=true]:border-error",
);

/** Compact controls for dense panels (planner rails, dialogs): same 44px height, 15px text. */
// 16px on touch screens: iOS Safari zooms the page into a smaller field on focus (D11 harden).
export const controlCompactClass = "min-h-11 rounded-[22px] px-4 py-2 text-body-sm pointer-coarse:text-body-md";

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
