/** Pieces shared by the feed's cards: course chips, the reason chip, the AI note, small actions. */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { SparkIcon } from "@/components/ui/icons";
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

/** Why the item is here (written by the feed's own rules, never by a model). */
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

/** The AI curator's line for this card, always labelled as AI. */
export function AiNote({ note }: { note: string }) {
  return (
    <p className="flex gap-2 border-l-2 border-primary/40 pl-3 font-display text-[17px] italic leading-snug text-body-strong">
      <SparkIcon size={14} className="mt-1 shrink-0 text-primary not-italic" />
      <span>
        {note} <span className="whitespace-nowrap font-sans text-caption not-italic text-muted">(AI note)</span>
      </span>
    </p>
  );
}

/** A small text action in a card's footer (44px tall target). */
export function CardAction({
  children,
  onClick,
  pressed,
  label,
}: {
  children: ReactNode;
  onClick: () => void;
  pressed?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      aria-label={label}
      className={cn(
        "inline-flex min-h-11 items-center gap-1.5 rounded-pill px-3 text-caption font-medium transition-colors",
        pressed ? "bg-primary-wash text-primary" : "text-muted hover:bg-surface-strong hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

export function BookmarkIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.75} strokeLinejoin="round">
      <path d="M6.5 4h11v16l-5.5-4-5.5 4z" />
    </svg>
  );
}

export function LessIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round">
      <circle cx={12} cy={12} r={8} />
      <path d="M8.5 12h7" />
    </svg>
  );
}

/** "Witty Trout · 3 days ago" style meta. */
export function Meta({ children }: { children: ReactNode }) {
  return <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">{children}</p>;
}
