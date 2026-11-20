import type { CSSProperties } from "react";
import { SparkIcon } from "@/components/ui/icons";

/**
 * Today's headline above the feed, revealed word by word (each word rises and settles). When a
 * model wrote it, it says so; otherwise it is the feed's own line.
 */
export function AiHeadline({ headline, ai, pending }: { headline: string; ai: boolean; pending: boolean }) {
  const words = headline.split(/\s+/).filter(Boolean);
  // "Today's river:" is set in the italic maroon of the page titles.
  const lead = words.slice(0, 3).findIndex((w) => w.endsWith(":"));
  return (
    <div className="flex min-h-[92px] flex-col gap-2">
      <p className="flex items-center gap-2 text-caption text-muted">
        {ai ? (
          <>
            <SparkIcon size={14} className="text-primary" />
            <span>Curated by the AI — can be wrong</span>
          </>
        ) : pending ? (
          <span>The curator is reading today’s river…</span>
        ) : (
          <span>Today’s river</span>
        )}
      </p>
      <h2 key={headline} className="font-display text-[28px] font-bold leading-[1.15] tracking-[-0.4px] text-ink text-balance sm:text-[36px]">
        <span className="sr-only">{headline}</span>
        <span aria-hidden="true">
          {words.map((w, i) => (
            <span key={`${i}-${w}`}>
              <span className="feed-headline-word" style={{ "--i": i } as CSSProperties}>
                {i <= lead ? <em className="text-primary">{w}</em> : w}
              </span>{" "}
            </span>
          ))}
        </span>
      </h2>
    </div>
  );
}
