import { cva, type VariantProps } from "class-variance-authority";
import type { CSSProperties, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

/*
 * DESIGN.md card family. Cards are white on the canvas with a 1px hairline; the only shadow is the
 * hover tier, and only on cards that are links or targets.
 */
export const cardVariants = cva("min-w-0 text-ink", {
  variants: {
    variant: {
      /** course-card: white, 16px radius, 24px padding. */
      default: "rounded-xl border border-hairline bg-surface-card p-6",
      /** Compact card (menus, dense lists): 12px radius, 16px padding. */
      compact: "rounded-lg border border-hairline bg-surface-card p-4",
      /** post-card: white, 16px radius, 32px padding, body text color. */
      post: "rounded-xl border border-hairline bg-surface-card p-8 text-body",
      /** orb-card: canvas-soft, 24px radius, 32px padding; pair with one <Orb>. */
      orb: "relative isolate overflow-hidden rounded-xxl bg-canvas-soft p-8",
      /** featured-card: the maroon inversion, at most one per page. */
      featured: "rounded-xl bg-surface-inverse p-8 text-on-primary",
      /** A quiet well for grouped controls (filters, a form step). */
      well: "rounded-xl border border-hairline bg-canvas-soft p-5",
    },
    interactive: {
      true: "transition-shadow hover:shadow-hover focus-within:shadow-hover",
      false: "",
    },
  },
  defaultVariants: { variant: "default", interactive: false },
});

type CardProps = HTMLAttributes<HTMLElement> &
  VariantProps<typeof cardVariants> & { as?: "div" | "section" | "article" | "li" | "aside" | "figure" };

export function Card({ as: Tag = "div", variant, interactive, className, ...props }: CardProps) {
  return <Tag className={cn(cardVariants({ variant, interactive }), className)} {...props} />;
}

export type OrbColor = "lake" | "goldenrod" | "ivy" | "terracotta" | "rose";

const ORB_VAR: Record<OrbColor, string> = {
  lake: "var(--color-orb-lake)",
  goldenrod: "var(--color-orb-goldenrod)",
  ivy: "var(--color-orb-ivy)",
  terracotta: "var(--color-orb-terracotta)",
  rose: "var(--color-orb-rose)",
};

/**
 * Atmosphere only: one orb-* color as a soft radial bloom (40% at the center, fading out, blurred
 * 70px). Never a surface. It does not move, so reduced motion needs nothing extra.
 */
export function Orb({ color, className, style }: { color: OrbColor; className?: string; style?: CSSProperties }) {
  return <div aria-hidden="true" className={cn("orb -z-10", className)} style={{ ["--orb-color" as string]: ORB_VAR[color], ...style }} />;
}

/** avatar: 32px circle on surface-strong with initials. Decorative next to a visible name. */
export function Avatar({ name, className }: { name: string; className?: string }) {
  const initials = name
    .split(/[\s_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  return (
    <span aria-hidden="true" className={cn("inline-flex size-8 shrink-0 items-center justify-center rounded-pill bg-surface-strong text-caption-uppercase text-ink", className)}>
      {initials || "?"}
    </span>
  );
}

/** A stat for attribute grids: caption label over a title value. */
export function Stat({ label, value, children }: { label: ReactNode; value: ReactNode; children?: ReactNode }) {
  return (
    <div className="rounded-lg bg-canvas-soft p-4">
      <dt className="text-caption text-muted">{label}</dt>
      <dd className="mt-0.5 text-title-sm tabular-nums">{value}</dd>
      {children}
    </div>
  );
}
