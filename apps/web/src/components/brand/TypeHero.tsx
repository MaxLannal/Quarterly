import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { GradientArt } from "./GradientArt";
import { TypeScape, type ShapeName } from "./TypeScape";

/**
 * The new pages' title (docs/BEST-OF-UCHICAGO-PLAN.md "Shared look"): a maroon uppercase kicker,
 * a Newsreader headline whose `<em>` words turn italic maroon, and a one-line subline.
 */
export function PageTitle({
  kicker,
  title,
  subline,
  as: Tag = "h1",
  size = "lg",
  className,
}: {
  kicker?: ReactNode;
  title: ReactNode;
  subline?: ReactNode;
  as?: "h1" | "h2";
  size?: "lg" | "md";
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-3", className)}>
      {kicker && (
        <p className="flex items-center gap-2 text-caption-uppercase uppercase text-primary">
          <span aria-hidden="true" className="inline-block h-px w-6 bg-primary" />
          {kicker}
        </p>
      )}
      <Tag
        className={cn(
          "page-title font-display font-extrabold text-ink text-balance",
          size === "lg"
            ? "text-[46px] leading-[1.02] tracking-[-1.8px] sm:text-[64px] sm:tracking-[-2.6px] xl:text-[72px]"
            : "text-[36px] leading-[1.06] tracking-[-1.1px] sm:text-display-xl",
        )}
      >
        {title}
      </Tag>
      {subline && <p className="max-w-[36rem] text-[19px] leading-[1.55] text-body">{subline}</p>}
    </div>
  );
}

/**
 * A page header in the redesign's manner (docs/DESIGN.md "Maroon and night"), after the reference
 * login card: the title and the page's main controls on the left; on the right a rounded art panel,
 * maroon, crimson and coral light on black, with a TypeScape figure of real course titles glowing
 * on it (point at a title to see its course; click to open it). On phones the panel comes first.
 */
export function TypeHero({
  shape,
  label,
  words,
  kicker,
  title,
  subline,
  children,
  className,
  tall = false,
}: {
  shape: ShapeName;
  label: string;
  words?: string[];
  /** Kept for callers of the earlier full-width hero; the panel centres its figure. */
  focus?: number;
  kicker?: ReactNode;
  title: ReactNode;
  subline?: ReactNode;
  children?: ReactNode;
  className?: string;
  /** A taller hero (most of the first screen). */
  tall?: boolean;
}) {
  return (
    <section
      className={cn(
        "mx-auto grid w-full max-w-content items-stretch gap-6 px-4 pb-8 pt-5 sm:px-6 sm:pt-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-12 lg:px-8 lg:pb-12 lg:pt-8",
        className,
      )}
    >
      <div className="order-2 flex min-w-0 flex-col justify-center gap-7 lg:order-1 lg:py-10">
        <PageTitle kicker={kicker} title={title} subline={subline} />
        {children}
      </div>
      <div
        className={cn(
          "relative isolate order-1 overflow-hidden rounded-[28px] shadow-overlay sm:rounded-art lg:order-2",
          tall ? "min-h-[300px] sm:min-h-[380px] lg:min-h-[620px]" : "min-h-[240px] sm:min-h-[320px] lg:min-h-[540px]",
        )}
      >
        <GradientArt seed={shape} />
        <TypeScape shape={shape} label={label} words={words} focus={0.5} theme="night" zoom={1.6} />
      </div>
    </section>
  );
}
