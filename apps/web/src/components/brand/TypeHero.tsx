import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { ShapeName } from "./TypeScape";

/**
 * A page title ("Simple light", docs/DESIGN.md): an optional small kicker, a medium-weight
 * headline whose `<em>` words turn grey, and a one-line subline.
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
    <div className={cn("flex min-w-0 flex-col gap-2", className)}>
      {kicker && <p className="text-caption font-medium text-muted">{kicker}</p>}
      <Tag className={cn("page-title text-ink text-balance", size === "lg" ? "text-display-md sm:text-display-lg" : "text-display-sm sm:text-display-md")}>
        {title}
      </Tag>
      {subline && <p className="max-w-[40rem] text-body-md text-body">{subline}</p>}
    </div>
  );
}

/**
 * A page header: the title and the page's main controls. (It used to carry an art panel of course
 * titles on maroon light; the simple design has none, so `shape`, `label` and `words` are unused.)
 */
export function TypeHero({
  kicker,
  title,
  subline,
  children,
  className,
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
  tall?: boolean;
}) {
  return (
    <section className={cn("mx-auto flex w-full max-w-content flex-col gap-5 px-4 pb-6 pt-6 sm:px-6 sm:pt-8 lg:px-8", className)}>
      <PageTitle kicker={kicker} title={title} subline={subline} />
      {children}
    </section>
  );
}
