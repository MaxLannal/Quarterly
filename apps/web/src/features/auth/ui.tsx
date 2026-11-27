import { useEffect, useId, useRef, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { TypeScape } from "@/components/brand/TypeScape";
import { standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { ArrowIcon, CheckIcon, ErrorIcon, EyeIcon, EyeOffIcon, MailIcon } from "@/components/ui/icons";
import { controlClass, FieldError, FieldHint } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import "./auth.css";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  label: string;
  hint?: ReactNode;
  /** Shown under the field and announced; also marks the input invalid. */
  error?: string | null;
  /** A decorative icon at the end of the pill (the reference's envelope). */
  icon?: "mail";
}

/** A labelled pill input with a mono capital label, a hint and an announced error. A password
 * field gets a button that shows or hides its characters. */
export function TextField({ label, hint, error, className, icon, type, ...input }: TextFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");
  const secret = type === "password";
  const [shown, setShown] = useState(false);
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="auth-label">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={secret && shown ? "text" : type}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          className={cn(controlClass, "auth-input", (icon || secret) && "pr-14", className)}
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
            className="absolute right-1.5 top-1/2 inline-flex size-11 -translate-y-1/2 items-center justify-center rounded-pill text-muted transition-colors duration-300 hover:bg-surface-strong hover:text-ink"
          >
            {shown ? <EyeOffIcon size={20} /> : <EyeIcon size={20} />}
          </button>
        ) : null}
      </div>
      {hint ? (
        <div className="pl-1.5">
          <FieldHint id={hintId}>{hint}</FieldHint>
        </div>
      ) : null}
      {error ? (
        <div className="pl-1.5">
          <FieldError id={errorId}>{error}</FieldError>
        </div>
      ) : null}
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
        <p className="flex items-start gap-3 rounded-[20px] bg-error-wash px-4 py-3 text-body-sm text-ink shadow-[inset_0_0_0_1px_rgb(255_143_128/0.22)]">
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
        <p className="flex items-start gap-3 rounded-[20px] bg-success-wash px-4 py-3 text-body-sm text-ink shadow-[inset_0_0_0_1px_rgb(185_214_144/0.2)]">
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
    <h2 ref={ref} tabIndex={-1} className="auth-step-heading outline-none">
      {children}
    </h2>
  );
}

/**
 * Sign-up and login (docs/DESIGN.md "Dark glass", after Max's reference of 2026-11-27): one large
 * card of dark glass floating centred on the night, the light at full strength around it and a ring
 * of it turning slowly behind. On wide screens a Gothic window drawn in real course titles glows
 * faintly behind the card. Inside: a mono chip, the big serif title, a soft subline, then the form.
 * Mono captions sit in the corners; they are decoration only (aria-hidden).
 */
export function AuthPage({
  title,
  chip = "Quarterly.account",
  eyebrow,
  steps,
  subline,
  children,
  wide = false,
}: {
  title: string;
  /** The small mono chip above the title. */
  chip?: string;
  /** A mono line under the title (sign-up: "Step 2 of 4"). */
  eyebrow?: ReactNode;
  /** The sign-up step indicator beside the eyebrow (decorative: the eyebrow says it in words). */
  steps?: { current: number; total: number };
  subline?: ReactNode;
  children: ReactNode;
  /** A wider column (36rem, not 30rem) for the long sign-up form (step 4), so a credit fits on
   * one line (Richard, 2026-11-25). */
  wide?: boolean;
}) {
  return (
    <section className="auth-stage">
      <AuthCaptions />
      <div className="auth-art">
        <TypeScape shape="arch" theme="night" zoom={1.25} focus={0.5} label="A Gothic window drawn with the titles of real courses" />
      </div>
      <div className="auth-frame" data-wide={wide ? "true" : undefined}>
        <div aria-hidden="true" className="auth-halo" />
        <div className="auth-card auth-rise">
          <header className="flex flex-col items-center gap-5 text-center">
            <span aria-hidden="true" className="auth-chip">
              {chip}
            </span>
            <h1 className="auth-title">{title}</h1>
            {subline && <p className="max-w-[26rem] text-balance text-body-md text-body">{subline}</p>}
          </header>
          {eyebrow || steps ? (
            <div className="auth-progress">
              {eyebrow && <p className="auth-progress-label">{eyebrow}</p>}
              {steps && (
                <div aria-hidden="true" className="auth-progress-track">
                  <span className="auth-progress-fill" style={{ width: `${((steps.current - 1) / Math.max(1, steps.total - 1)) * 100}%` }} />
                  {Array.from({ length: steps.total }, (_, i) => (
                    <i
                      key={i}
                      data-on={i < steps.current ? "true" : undefined}
                      data-current={i === steps.current - 1 ? "true" : undefined}
                      style={{ left: `${(i / Math.max(1, steps.total - 1)) * 100}%` }}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : null}
          <div className={cn("mx-auto flex w-full flex-col gap-5", wide ? "max-w-[36rem]" : "max-w-[30rem]")}>{children}</div>
        </div>
      </div>
    </section>
  );
}

/** The corner captions: what the page is, in the manner of an instrument panel. Decorative. */
function AuthCaptions() {
  return (
    <>
      <p aria-hidden="true" className="auth-caption auth-caption-tl">
        <span className="auth-lamp" />
        Quarterly // UChicago
      </p>
      <p aria-hidden="true" className="auth-caption auth-caption-tr">
        Catalog 2026-27
      </p>
      <p aria-hidden="true" className="auth-caption auth-caption-bl">
        Secure session
      </p>
      <p aria-hidden="true" className="auth-caption auth-caption-br auth-caret">
        Autumn · Winter · Spring
      </p>
    </>
  );
}

/** The rule between the form and the other way in: a mono word between two fading hairlines. */
export function OrDivider({ label = "or" }: { label?: string }) {
  return (
    <div className="auth-divider" aria-hidden="true">
      {label}
    </div>
  );
}

/** The main button of an auth form: a full-width white pill in mono capitals, with an arrow. */
export function SubmitButton({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <Button type="submit" disabled={busy} className="auth-submit w-full">
      {children}
      {busy ? null : <ArrowIcon size={16} />}
    </Button>
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
