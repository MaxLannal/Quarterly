import { useEffect, useId, useRef, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { GradientArt } from "@/components/brand/GradientArt";
import { TypeScape } from "@/components/brand/TypeScape";
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

/** The brand emblem above the sign-in title: a Gothic window in maroon (the reference's house). */
function ArchMark() {
  return (
    <svg aria-hidden="true" width="44" height="52" viewBox="0 0 44 52" className="text-primary">
      <path d="M4 50V22C4 11 12 3 22 2c10 1 18 9 18 20v28z" fill="currentColor" />
      <path d="M10 50V23c0-7 5-12.5 12-13.5 7 1 12 6.5 12 13.5v27z" fill="#fff" opacity=".18" />
      <path d="M22 10v40M10 30h24" stroke="#fff" strokeWidth="2" opacity=".55" />
      <circle cx="22" cy="21" r="4.5" fill="none" stroke="#fff" strokeWidth="2" opacity=".7" />
    </svg>
  );
}

/**
 * Sign-up and login (docs/DESIGN.md "Maroon and night", after the reference login card): on the
 * white sheet, the form centred on the left under a maroon emblem and a big bold title; on the
 * right a rounded art panel with a Gothic window drawn in glowing course titles (wide screens).
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
    <section className="mx-auto grid w-full max-w-content gap-6 p-3 sm:p-5 lg:min-h-[760px] lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-8">
      <div className="flex flex-col justify-center px-3 py-10 sm:px-10 lg:py-16">
        <div className={cn("mx-auto flex w-full flex-col gap-8", wide ? "max-w-[36rem]" : "max-w-[30rem]")}>
          <div className="flex flex-col items-center gap-4 text-center">
            <ArchMark />
            {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
            <h1 className="font-display text-[44px] font-extrabold leading-[1.02] tracking-[-1.8px] sm:text-[54px]">
              {title}
            </h1>
            {subline && <p className="text-body-md text-body">{subline}</p>}
          </div>
          <div className="flex flex-col gap-5">{children}</div>
        </div>
      </div>
      <div className="relative isolate hidden overflow-hidden rounded-art shadow-overlay lg:block">
        <GradientArt seed={title} />
        <TypeScape
          shape="arch"
          theme="night"
          zoom={1.7}
          focus={0.5}
          label="A Gothic window drawn with the titles of real courses"
        />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-night via-night/80 to-transparent px-9 pb-9 pt-24">
          <p className="font-serif text-[28px] italic leading-snug text-on-night">
            Every course of the College, in one place you can plan from.
          </p>
        </div>
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
