import { cva, type VariantProps } from "class-variance-authority";
import type { CSSProperties, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

/*
 * DESIGN.md card family ("Dark glass"). Cards are glass tints on the pane with a rim of light (a
 * 1px gradient ring, `.glass-rim`) instead of a flat border; the only shadow is the hover tier,
 * and only on cards that are links or targets.
 */
export const cardVariants = cva("min-w-0 text-ink", {
  variants: {
    variant: {
      /** course-card: a glass tile with a lit top edge, 18px radius, 24px padding. */
      default: "glass-rim rounded-xl bg-surface-card p-6",
      /** Compact card (menus, dense lists). */
      compact: "glass-rim rounded-lg bg-surface-card p-4",
      /** post-card: glass, 32px padding, body text colour. */
      post: "glass-rim rounded-xl bg-surface-card p-8 text-body",
      /** orb-card: glass with one red bloom inside; pair with one <Orb>. */
      orb: "glass-rim isolate overflow-hidden rounded-xxl bg-canvas-soft p-8",
      /** featured-card: deep maroon glass, at most one per page. */
      featured:
        "rounded-xl border border-[rgb(255_120_140/0.25)] bg-[linear-gradient(160deg,#7a1228,#3a0712)] p-8 text-on-dark shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_24px_60px_rgb(120_10_30/0.35)]",
      /** A quiet well for grouped controls (filters, a form step). */
      well: "glass-rim rounded-xl bg-canvas-soft p-5",
    },
    interactive: {
      true: "transition-[box-shadow,translate] duration-300 hover:-translate-y-0.5 hover:shadow-hover focus-within:shadow-hover",
      false: "",
    },
  },
  defaultVariants: { variant: "default", interactive: false },
});

type CardProps = HTMLAttributes<HTMLElement> &
  VariantProps<typeof cardVariants> & { as?: "div" | "section" | "article" | "li" | "aside" | "figure" };

export function Card({ as: Tag = "div", variant, interactive, className, ...props }: CardProps) {
  return <Tag data-spotlight={interactive ? "" : undefined} className={cn(cardVariants({ variant, interactive }), className)} {...props} />;
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
    <span aria-hidden="true" className={cn("inline-flex size-8 shrink-0 items-center justify-center rounded-pill bg-[linear-gradient(160deg,rgb(255_92_112/0.35),rgb(120_10_32/0.5))] text-caption-uppercase text-ink shadow-[inset_0_0_0_1px_rgb(255_255_255/0.14)]", className)}>
      {initials || "?"}
    </span>
  );
}

/** A stat for attribute grids: caption label over a title value. */
export function Stat({ label, value, children }: { label: ReactNode; value: ReactNode; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-hairline-soft bg-canvas-soft p-4">
      <dt className="text-caption text-muted">{label}</dt>
      <dd className="mt-0.5 text-title-sm tabular-nums">{value}</dd>
      {children}
    </div>
  );
}
