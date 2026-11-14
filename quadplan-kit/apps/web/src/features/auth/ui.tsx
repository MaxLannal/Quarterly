import { useEffect, useId, useRef, type InputHTMLAttributes, type ReactNode } from "react";
import { Eyebrow, PageContainer, standaloneLinkClass } from "@/components/layout/page";
import { CheckIcon, ErrorIcon } from "@/components/ui/icons";
import { controlClass, FieldError, FieldHint, Label } from "@/components/ui/input";
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
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={cn(controlClass, className)}
        {...input}
      />
      {hint ? <FieldHint id={hintId}>{hint}</FieldHint> : null}
      {error ? <FieldError id={errorId}>{error}</FieldError> : null}
    </div>
  );
}

/** Form-level error: announced as soon as it appears. */
export function FormError({ message }: { message: string | null }) {
  return (
    <div role="alert" aria-live="assertive">
      {message ? (
        <p className="flex items-start gap-3 rounded-lg border border-error/30 bg-error-wash px-4 py-3 text-body-sm text-ink">
          <ErrorIcon className="mt-[3px] shrink-0 text-error" />
          <span>{message}</span>
        </p>
      ) : null}
    </div>
  );
}

/** Polite status message (success, "code sent"). */
export function Notice({ message }: { message: string | null }) {
  return (
    <div role="status" aria-live="polite">
      {message ? (
        <p className="flex items-start gap-3 rounded-lg border border-success/25 bg-success-wash px-4 py-3 text-body-sm text-ink">
          <CheckIcon className="mt-[3px] shrink-0 text-success" />
          <span>{message}</span>
        </p>
      ) : null}
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
    <h2 ref={ref} tabIndex={-1} className="font-display text-display-sm outline-none">
      {children}
    </h2>
  );
}

/** Sign-up and login: a narrow form column on a white card. */
export function AuthPage({ title, eyebrow, children }: { title: string; eyebrow?: ReactNode; children: ReactNode }) {
  return (
    <PageContainer width="form" as="section" className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
        <h1 className="font-display text-display-md">{title}</h1>
      </div>
      <div className="flex flex-col gap-5 rounded-xl border border-hairline bg-surface-card p-6 sm:p-8">{children}</div>
    </PageContainer>
  );
}

export const linkClass = standaloneLinkClass;

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
