import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { CheckIcon, ErrorIcon, InfoIcon, WarningIcon } from "./icons";

/** Semantic tones from DESIGN.md "Semantic". `neutral` is the default badge-pill plate. */
const BADGE_TONES = {
  neutral: "bg-surface-strong text-ink shadow-[inset_0_0_0_1px_var(--color-hairline)]",
  success: "bg-success-wash text-success",
  warning: "bg-warning-wash text-warning",
  error: "bg-error-wash text-error",
  info: "bg-info-wash text-info",
} as const;

export type Tone = keyof typeof BADGE_TONES;

const TONE_ICON: Record<Tone, ReactNode> = {
  neutral: null,
  success: <CheckIcon size={14} />,
  warning: <WarningIcon size={14} className="text-warning-icon" />,
  error: <ErrorIcon size={14} />,
  info: <InfoIcon size={14} />,
};

/**
 * badge-pill: surface-strong plate, caption-uppercase, pill. Department and quarter tags use the
 * neutral tone; the semantic tones are for statuses (verifier, "In review", estimates) and always
 * carry an icon, so color is never the only signal.
 */
export function Badge({
  tone = "neutral",
  children,
  className,
  casing = "upper",
  icon = true,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  /** `normal` for sentence-case statuses such as "3 warnings". */
  casing?: "upper" | "normal";
  icon?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-pill px-[10px] py-1",
        casing === "upper" ? "text-caption-uppercase uppercase" : "text-caption font-medium",
        BADGE_TONES[tone],
        className,
      )}
    >
      {icon && TONE_ICON[tone]}
      {children}
    </span>
  );
}

const NOTICE_TONES: Record<Tone, string> = {
  neutral: "border-hairline bg-white/[0.035]",
  success: "border-success/25 bg-success-wash",
  warning: "border-warning/25 bg-warning-wash",
  error: "border-error/30 bg-error-wash",
  info: "border-info/25 bg-info-wash",
};

const NOTICE_ICON: Record<Tone, ReactNode> = {
  neutral: <InfoIcon className="text-gray-dark" />,
  success: <CheckIcon className="text-success" />,
  warning: <WarningIcon className="text-warning-icon" />,
  error: <ErrorIcon className="text-error" />,
  info: <InfoIcon className="text-info" />,
};

/** An inline message box with an icon. `role="status"` for live info, `alert` for errors. */
export function Notice({
  tone = "neutral",
  children,
  role,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  role?: "status" | "alert";
  className?: string;
}) {
  return (
    <div role={role} className={cn("flex items-start gap-3 rounded-lg border px-4 py-3 text-body-sm text-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.05)]", NOTICE_TONES[tone], className)}>
      <span className="mt-[3px] shrink-0">{NOTICE_ICON[tone]}</span>
      <div className="min-w-0 flex-1 [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2">{children}</div>
    </div>
  );
}

/** Shown wherever an endpoint answers 501 (feature not built yet). */
export function NotAvailable({ feature, children }: { feature: string; children?: ReactNode }) {
  return (
    <Notice tone="neutral" role="status">
      <strong className="font-medium">{feature} is not available yet.</strong> {children}
    </Notice>
  );
}

/** Inline loading line (DESIGN.md leaves loading states to us: muted caption + a plate). */
export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" className="flex items-center gap-2 text-caption text-muted">
      <span aria-hidden="true" className="inline-block size-2 animate-pulse rounded-pill bg-primary shadow-[0_0_10px_var(--color-primary)]" />
      {label}…
    </p>
  );
}

/** Inline error text: icon + message (never color alone). */
export function ErrorText({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("flex items-start gap-2 text-caption text-error", className)}>
      <ErrorIcon className="mt-[3px] shrink-0" size={14} />
      <span>{children}</span>
    </p>
  );
}

/** Rating dots for a 1–5 value, with the number for screen readers. Single series = maroon. */
export function Dots({ value, max = 5, label }: { value: number; max?: number; label: string }) {
  const filled = Math.round(value);
  return (
    <span className="inline-flex items-center gap-[3px]" title={`${label}: ${value.toFixed(1)} of ${max}`}>
      <span className="sr-only">{`${label} ${value.toFixed(1)} of ${max}`}</span>
      {Array.from({ length: max }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={cn("inline-block size-1.5 rounded-pill", i < filled ? "bg-primary shadow-[0_0_6px_rgb(255_92_112/0.6)]" : "bg-hairline-strong")}
        />
      ))}
    </span>
  );
}

/** A course code: caption-uppercase or tabular Inter, never the serif. */
export function CourseCode({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("font-mono text-[12.5px] font-medium uppercase tracking-[0.08em] tabular-nums text-muted", className)}>{children}</span>;
}
