import { useEffect, useId, useRef, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { Eyebrow, standaloneLinkClass } from "@/components/layout/page";
import { CheckIcon, ErrorIcon, EyeIcon, EyeOffIcon, MailIcon } from "@/components/ui/icons";
import { controlClass, FieldError, FieldHint, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  label: string;
  hint?: ReactNode;
  /** Shown under the field and announced; also marks the input invalid. */
  error?: string | null;
  /** A decorative icon at the end of the pill (the reference's envelope). */
  icon?: "mail";
}

/** A labelled pill input with a hint and an announced error. A password field gets a button that
 * shows or hides its characters (the reference's eye). */
export function TextField({ label, hint, error, className, icon, type, ...input }: TextFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");
  const secret = type === "password";
  const [shown, setShown] = useState(false);
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <input
          id={id}
          type={secret && shown ? "text" : type}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          className={cn(controlClass, (icon || secret) && "pr-14", className)}
          {...input}
        />
        {icon === "mail" && !secret ? (
          <MailIcon size={20} className="pointer-events-none absolute right-5 top-1/2 -translate-y-1/2 text-muted" />
        ) : null}
        {secret ? (
          <button
            type="button"
            aria-label={shown ? "Hide characters" : "Show characters"}
            aria-pressed={shown}
            aria-controls={id}
            onClick={() => setShown((v) => !v)}
            className="absolute right-1.5 top-1/2 inline-flex size-11 -translate-y-1/2 items-center justify-center rounded-pill text-muted transition-colors hover:bg-surface-strong hover:text-ink"
          >
            {shown ? <EyeOffIcon size={20} /> : <EyeIcon size={20} />}
          </button>
        ) : null}
      </div>
      {hint ? <FieldHint id={hintId}>{hint}</FieldHint> : null}
      {error ? <FieldError id={errorId}>{error}</FieldError> : null}
    </div>
  );
}

/** Form-level error: announced as soon as it appears. */
export function FormError({ message }: { message: string | null }) {
  return (
    // Empty live regions stay in the page (so later messages are announced) but leave the
    // flow, so they add no gap to the flex column around them.
    <div role="alert" aria-live="assertive" className="empty:absolute">
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
    <div role="status" aria-live="polite" className="empty:absolute">
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

/**
 * Sign-up and login ("Simple light", docs/DESIGN.md): one white card with a hairline, centred in the
 * panel, the black Q tile above a medium-weight title.
 */
export function AuthPage({
  title,
  eyebrow,
  subline,
  children,
  wide = false,
}: {
  title: string;
  eyebrow?: ReactNode;
  subline?: ReactNode;
  children: ReactNode;
  /** A wider column (36rem, not 30rem) for the long sign-up form (step 4), so a credit fits on
   * one line (Richard, 2026-11-25). */
  wide?: boolean;
}) {
  return (
    <section className="flex w-full justify-center px-4 py-10 sm:px-6 lg:py-16">
      <div className={cn("flex w-full flex-col gap-7 rounded-xxl border border-hairline bg-canvas p-6 sm:p-9", wide ? "max-w-[38rem]" : "max-w-[32rem]")}>
        <div className="flex flex-col items-center gap-3 text-center">
          <span aria-hidden="true" className="flex size-11 items-center justify-center rounded-xl bg-ink text-[20px] font-semibold text-on-primary">
            Q
          </span>
          {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
          <h1 className="text-display-md">{title}</h1>
          {subline && <p className="text-body-sm text-muted">{subline}</p>}
        </div>
        <div className="flex flex-col gap-5">{children}</div>
      </div>
    </section>
  );
}

/** The "or" rule between the form and the other way in (the reference's divider). */
export function OrDivider() {
  return (
    <div className="flex items-center gap-4 text-caption text-muted" aria-hidden="true">
      <span className="h-px flex-1 bg-hairline" />
      or
      <span className="h-px flex-1 bg-hairline" />
    </div>
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
