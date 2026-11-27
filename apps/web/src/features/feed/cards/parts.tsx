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
        "bg-white/[0.05] px-3.5 text-caption text-body shadow-[inset_0_0_0_1px_rgb(255_255_255/0.09),inset_0_1px_0_rgb(255_255_255/0.08)] transition-[color,box-shadow] duration-300 hover:text-ink hover:shadow-[inset_0_0_0_1px_rgb(255_120_140/0.45),inset_0_1px_0_rgb(255_255_255/0.1)]",
        className,
      )}
      title={title ? `${code} ${title}` : code}
    >
      <span className="shrink-0 font-mono text-[11.5px] font-medium uppercase tracking-[0.12em] text-ink">{code}</span>
      {title && <span className="truncate">{title}</span>}
    </Link>
  );
}

/** Why the item is here (written by the server's own rules, never by a model). */
export function ReasonChip({ children, dark = false }: { children: ReactNode; dark?: boolean }) {
  return (
    <p
      className={cn(
        "inline-flex max-w-full items-center gap-2 rounded-pill px-3 py-1 text-caption font-medium shadow-[inset_0_0_0_1px_rgb(255_120_140/0.22)]",
        dark ? "bg-surface-card/90 text-primary" : "bg-[linear-gradient(90deg,rgb(255_92_112/0.16),rgb(255_92_112/0.05))] text-primary",
      )}
    >
      <span aria-hidden="true" className="qg-dot" />
      <span className="min-w-0">{children}</span>
    </p>
  );
}

/** "Witty Trout · 3 days ago" style meta. */
export function Meta({ children }: { children: ReactNode }) {
  return <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">{children}</p>;
}
