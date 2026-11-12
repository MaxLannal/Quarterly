import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const TONES = {
  neutral: "border-border bg-muted text-foreground",
  green: "border-green-700 bg-green-50 text-green-900",
  amber: "border-amber-600 bg-amber-50 text-amber-900",
  red: "border-red-700 bg-red-50 text-red-900",
  blue: "border-blue-700 bg-blue-50 text-blue-900",
} as const;

export type Tone = keyof typeof TONES;

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium", TONES[tone], className)}>
      {children}
    </span>
  );
}

/** An inline message box. `role="status"` for live info, `alert` for errors. */
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
    <div role={role} className={cn("rounded-md border px-3 py-2 text-sm", TONES[tone], className)}>
      {children}
    </div>
  );
}

/** Shown wherever an endpoint answers 501 (feature not built yet). */
export function NotAvailable({ feature, children }: { feature: string; children?: ReactNode }) {
  return (
    <Notice tone="neutral" role="status">
      <strong>{feature} is not available yet.</strong> {children}
    </Notice>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" className="text-sm text-muted-foreground">
      {label}…
    </p>
  );
}

/** Rating dots for a 1–5 value, with the number for screen readers. */
export function Dots({ value, max = 5, label }: { value: number; max?: number; label: string }) {
  const filled = Math.round(value);
  return (
    <span className="inline-flex items-center gap-0.5" title={`${label}: ${value.toFixed(1)} of ${max}`}>
      <span className="sr-only">{`${label} ${value.toFixed(1)} of ${max}`}</span>
      {Array.from({ length: max }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={cn("inline-block size-1.5 rounded-full", i < filled ? "bg-foreground" : "bg-zinc-300")}
        />
      ))}
    </span>
  );
}
