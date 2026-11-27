import { cva, type VariantProps } from "class-variance-authority";
import type { CSSProperties, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

/*
 * Card family ("Simple light"): white with a 1px hairline and 16px corners; the only shadow is a
 * faint hover lift, and only on cards that are links or targets.
 */
export const cardVariants = cva("min-w-0 text-ink", {
  variants: {
    variant: {
      /** course-card: white, 16px radius, 24px padding, a hairline. */
      default: "rounded-xl border border-hairline bg-surface-card p-6",
      /** Compact card (menus, dense lists). */
      compact: "rounded-lg border border-hairline bg-surface-card p-4",
      /** post-card: white, 28px padding, body text colour. */
      post: "rounded-xl border border-hairline bg-surface-card p-7 text-body",
      /** orb-card (orbs are off): a soft grey card. */
      orb: "relative isolate overflow-hidden rounded-xl bg-canvas-soft p-7",
      /** featured-card: black, at most one per page (like the reference's "Download App" card). */
      featured: "rounded-xl bg-surface-inverse p-7 text-on-dark",
      /** A quiet grey well for grouped controls (filters, a form step). */
      well: "rounded-xl bg-canvas-soft p-5",
    },
    interactive: {
      true: "transition-[box-shadow,border-color] duration-200 hover:border-hairline-strong hover:shadow-hover focus-within:shadow-hover",
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

export type OrbColor = "lake" | "goldenrod" | "ivy" | "terracotta" | "rose" | "maroon";

const ORB_VAR: Record<OrbColor, string> = {
  lake: "var(--color-orb-lake)",
  goldenrod: "var(--color-orb-goldenrod)",
  ivy: "var(--color-orb-ivy)",
  terracotta: "var(--color-orb-terracotta)",
  rose: "var(--color-orb-rose)",
  maroon: "var(--color-orb-maroon)",
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
    <span aria-hidden="true" className={cn("inline-flex size-8 shrink-0 items-center justify-center rounded-pill bg-ink text-[12px] font-semibold text-on-primary", className)}>
      {initials || "?"}
    </span>
  );
}

/** A stat for attribute grids: caption label over a title value. */
export function Stat({ label, value, children }: { label: ReactNode; value: ReactNode; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-hairline bg-canvas p-4">
      <dt className="text-caption text-muted">{label}</dt>
      <dd className="mt-1 text-[24px] font-semibold leading-tight tracking-[-0.4px] tabular-nums">{value}</dd>
      {children}
    </div>
  );
}
