import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const WIDTHS = {
  /** 1200px content width (DESIGN.md "Grid & container"). */
  content: "max-w-content",
  /** 720px reading column for long text. */
  reading: "max-w-reading",
  /** Narrow column for sign-up and login forms. */
  form: "max-w-form",
  /** The planner's three rails (a recorded deviation from 1200px). */
  tool: "max-w-tool",
} as const;

export type PageWidth = keyof typeof WIDTHS;

/** Page container: centred, a 16/24/32px gutter, generous top and bottom space. */
export function PageContainer({
  width = "content",
  as: Tag = "div",
  className,
  children,
}: {
  width?: PageWidth;
  as?: "div" | "section" | "article";
  className?: string;
  children: ReactNode;
}) {
  return <Tag className={cn("mx-auto w-full px-4 pb-24 pt-8 sm:px-6 sm:pt-12 lg:px-8", WIDTHS[width], className)}>{children}</Tag>;
}

/** Section label: caption-uppercase, muted (e.g. "COURSE", "STEP 2 OF 5"). */
export function Eyebrow({ children, className, as: Tag = "p" }: { children: ReactNode; className?: string; as?: "p" | "span" | "div" }) {
  return <Tag className={cn("text-caption-uppercase uppercase text-muted", className)}>{children}</Tag>;
}

const TITLE_SIZES = {
  xl: "text-display-md sm:text-display-xl",
  lg: "text-display-md sm:text-display-lg",
  md: "text-display-sm sm:text-display-md",
} as const;

/**
 * Page header: optional eyebrow, a Newsreader 300 h1, a body-md description and actions.
 * Display type is never bold.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
  size = "lg",
  className,
  children,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  size?: keyof typeof TITLE_SIZES;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <header className={cn("mb-10 flex flex-col gap-4", className)}>
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h1 className={cn("font-display text-ink", TITLE_SIZES[size])}>{title}</h1>
      {meta && <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-caption text-muted">{meta}</div>}
      {description && <div className="max-w-reading text-body-md text-body">{description}</div>}
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
      {children}
    </header>
  );
}

const SECTION_TITLES = {
  lg: "font-display text-display-sm sm:text-display-md",
  md: "font-display text-display-sm",
  sm: "text-title-sm",
} as const;

/** A titled page section with 48px between sections (96px between page bands). */
export function Section({
  id,
  title,
  description,
  actions,
  size = "md",
  className,
  children,
  "aria-label": ariaLabel,
}: {
  id?: string;
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  size?: keyof typeof SECTION_TITLES;
  className?: string;
  children: ReactNode;
  "aria-label"?: string;
}) {
  const headingId = id ? `${id}-heading` : undefined;
  return (
    <section aria-labelledby={title ? headingId : undefined} aria-label={title ? undefined : ariaLabel} className={cn("min-w-0", className)}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h2 id={headingId} className={cn("text-ink", SECTION_TITLES[size])}>
                {title}
              </h2>
            )}
            {description && <p className="mt-1 text-body-sm text-muted">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/** Empty state: a dashed hairline plate, muted text, an optional action. */
export function EmptyState({ title, children, action, className }: { title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-start gap-2 rounded-xl border border-dashed border-hairline-strong bg-canvas-soft px-5 py-6", className)}>
      {title && <p className="text-body-strong text-ink">{title}</p>}
      {children && <div className="text-body-sm text-muted [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2">{children}</div>}
      {action}
    </div>
  );
}

/** Loading skeleton: surface-strong plates plus an announced label. */
export function LoadingState({ label, lines = 3, className }: { label: string; lines?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <p role="status" className="text-caption text-muted">
        {label}…
      </p>
      <div aria-hidden="true" className="flex flex-col gap-3">
        {Array.from({ length: lines }, (_, i) => (
          <div key={i} className="skeleton h-16" style={{ width: `${100 - i * 12}%` }} />
        ))}
      </div>
    </div>
  );
}

/** link-inline: maroon, underlined. Standalone links also get a 44px target. */
export const inlineLinkClass = "rounded-xs text-primary underline underline-offset-2 hover:text-primary-hover";
export const standaloneLinkClass = cn(inlineLinkClass, "inline-flex min-h-11 items-center");
