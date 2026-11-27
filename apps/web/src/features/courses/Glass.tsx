/**
 * Glass pieces shared by the catalog, course, program, instructor and forum pages (docs/DESIGN.md
 * "Dark glass"): two-line fact chips, a mono kicker, a rating ring and a thin meter. Styles live in
 * glass.css next to this file.
 */
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import "./glass.css";

/** A row of two-line glass chips (a `<dl>`): each chip is a tiny mono label over a value. */
export function FactChips({ children, className, label }: { children: ReactNode; className?: string; label?: string }) {
  return (
    <dl aria-label={label} className={cn("qg-facts", className)}>
      {children}
    </dl>
  );
}

/** One fact: "UNITS" over "100". `tone="ember"` lights the one chip that matters most. */
export function FactChip({ label, children, tone, className }: { label: ReactNode; children: ReactNode; tone?: "ember"; className?: string }) {
  return (
    <div className={cn("qg-chip", className)} data-tone={tone}>
      <dt className="qg-chip-label">{label}</dt>
      <dd className="qg-chip-value">{children}</dd>
    </div>
  );
}

/** A mono kicker with a short lit rule: "CATALOG // 2099-00". */
export function Kicker({ children, className, as: Tag = "p" }: { children: ReactNode; className?: string; as?: "p" | "span" | "div" }) {
  return <Tag className={cn("qg-kicker", className)}>{children}</Tag>;
}

/**
 * A rating as a ring of red light: the share of the ring is `value / max`. Decorative: the number
 * beside or inside it is the text, so the SVG is hidden from assistive technology.
 */
export function RatingRing({ value, max = 5, size = 64, stroke = 5, className, children }: { value: number | null | undefined; max?: number; size?: number; stroke?: number; className?: string; children?: ReactNode }) {
  const gid = `qg-ring-${useId().replace(/:/g, "")}`;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const share = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  return (
    <span className={cn("relative inline-flex shrink-0 items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false" className="absolute inset-0 -rotate-90">
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ffc2ca" />
            <stop offset="55%" stopColor="#ff5c70" />
            <stop offset="100%" stopColor="#a3122f" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth={stroke} />
        {share > 0 && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={`url(#${gid})`}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${c * share} ${c}`}
            style={{ filter: "drop-shadow(0 0 4px rgb(255 92 112 / 0.7))" }}
          />
        )}
      </svg>
      {children && <span className="relative">{children}</span>}
    </span>
  );
}

/** A thin lit meter for a share (0-1). Decorative; pair it with the number as text. */
export function Meter({ share, className }: { share: number; className?: string }) {
  return (
    <span aria-hidden="true" className={cn("qg-meter block", className)}>
      <span style={{ width: `${Math.max(0, Math.min(1, share)) * 100}%` }} />
    </span>
  );
}
