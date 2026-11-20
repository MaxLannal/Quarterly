import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
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
          "page-title font-display font-normal text-ink text-balance",
          size === "lg"
            ? "text-[44px] leading-[1.02] tracking-[-1.2px] sm:text-[64px] sm:tracking-[-1.92px]"
            : "text-[34px] leading-[1.08] tracking-[-0.6px] sm:text-display-xl",
        )}
      >
        {title}
      </Tag>
      {subline && <p className="max-w-[38rem] text-body-md text-body">{subline}</p>}
    </div>
  );
}

/**
 * A page header in the chapel's manner: a TypeScape figure on the right (behind the content on
 * phones), the title and the page's main controls on the left over a soft paper veil.
 */
export function TypeHero({
  shape,
  label,
  words,
  focus,
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
        "relative isolate overflow-hidden border-b border-hairline",
        tall ? "min-h-[min(78svh,760px)]" : "min-h-[440px] sm:min-h-[480px]",
        className,
      )}
    >
      <TypeScape shape={shape} label={label} words={words} focus={focus} />
      {/* The veil keeps the text readable where the titles run under it. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 bg-[linear-gradient(90deg,var(--color-canvas)_0%,color-mix(in_srgb,var(--color-canvas)_88%,transparent)_38%,transparent_62%)] max-[899px]:bg-[linear-gradient(180deg,color-mix(in_srgb,var(--color-canvas)_30%,transparent)_0%,color-mix(in_srgb,var(--color-canvas)_92%,transparent)_55%,var(--color-canvas)_100%)]"
      />
      <div
        className={cn(
          "pointer-events-none mx-auto flex w-full max-w-content px-4 sm:px-6 lg:px-8",
          tall ? "min-h-[min(78svh,760px)]" : "min-h-[440px] sm:min-h-[480px]",
          "items-end pb-10 pt-40 min-[900px]:items-center min-[900px]:py-16",
        )}
      >
        <div className="pointer-events-auto flex w-full max-w-[36rem] flex-col gap-6">
          <PageTitle kicker={kicker} title={title} subline={subline} />
          {children}
        </div>
      </div>
    </section>
  );
}
