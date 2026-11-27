/** Pieces shared by the browse rows' cards: course chips, the reason chip and the meta line. */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { courseHref } from "../api";

/** A course as a pill link (only codes the API returned, so the page exists). */
export function CourseChip({ code, title, className }: { code: string; title?: string; className?: string }) {
  return (
    <Link
      to={courseHref(code)}
      className={cn(
        "inline-flex min-h-11 max-w-full items-center gap-2 rounded-pill border-2 border-transparent bg-clip-padding",
        "bg-surface-strong px-3 text-caption text-ink transition-colors hover:bg-primary-wash hover:text-primary",
        className,
      )}
      title={title ? `${code} ${title}` : code}
    >
      <span className="shrink-0 text-caption-uppercase uppercase">{code}</span>
      {title && <span className="truncate">{title}</span>}
    </Link>
  );
}

/** Why the item is here (written by the server's own rules, never by a model). */
export function ReasonChip({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
  return (
    <p
      className={cn(
        "inline-flex max-w-full items-center gap-2 rounded-pill px-3 py-1 text-caption font-medium",
        dark ? "bg-surface-card/90 text-primary" : "bg-primary-wash text-primary",
      )}
    >
      <span aria-hidden="true" className="inline-block size-1.5 shrink-0 rounded-pill bg-primary" />
      <span className="min-w-0">{children}</span>
    </p>
  );
}

/** "Witty Trout · 3 days ago" style meta. */
export function Meta({ children }: { children: ReactNode }) {
  return <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">{children}</p>;
}
