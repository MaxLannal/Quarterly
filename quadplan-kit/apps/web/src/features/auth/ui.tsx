import { useEffect, useId, useRef, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  label: string;
  hint?: ReactNode;
  /** Shown under the field and announced; also marks the input invalid. */
  error?: string | null;
}

/** A labelled input with a hint and an announced error, at least 44px tall. */
export function TextField({ label, hint, error, className, ...input }: TextFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={cn(
          "min-h-11 rounded-md border border-border bg-background px-3 text-base",
          "focus-visible:outline-2 focus-visible:outline-offset-2",
          error && "border-primary",
          className,
        )}
        {...input}
      />
      {hint ? (
        <p id={hintId} className="text-sm text-muted-foreground">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-sm font-medium text-primary">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Form-level error: announced as soon as it appears. */
export function FormError({ message }: { message: string | null }) {
  return (
    <div role="alert" aria-live="assertive">
      {message ? (
        <p className="rounded-md border border-primary bg-muted p-3 text-sm font-medium text-primary">
          {message}
        </p>
      ) : null}
    </div>
  );
}

/** Polite status message (success, "code sent"). */
export function Notice({ message }: { message: string | null }) {
  return (
    <div role="status" aria-live="polite">
      {message ? <p className="rounded-md border border-border bg-muted p-3 text-sm">{message}</p> : null}
    </div>
  );
}

/** A step or section heading that takes focus when it appears, so screen readers follow. */
export function StepHeading({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return (
    <h2 ref={ref} tabIndex={-1} className="text-lg font-semibold outline-none">
      {children}
    </h2>
  );
}

export function AuthPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mx-auto flex max-w-md flex-col gap-4 p-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {children}
    </section>
  );
}

export const linkClass = "inline-flex min-h-11 items-center text-primary underline";

export const PASSWORD_MIN = 12;
export const PASSWORD_HINT = `At least ${PASSWORD_MIN} characters. A few unrelated words work well.`;

/** Client-side checks that mirror the API schema; the server checks again. */
export function passwordProblem(password: string, confirm: string): string | null {
  if (password.length < PASSWORD_MIN) return `Use at least ${PASSWORD_MIN} characters.`;
  if (password.length > 256) return "Use at most 256 characters.";
  if (password !== confirm) return "The two passwords do not match.";
  return null;
}

export const CODE_PATTERN = /^\d{6}$/;
