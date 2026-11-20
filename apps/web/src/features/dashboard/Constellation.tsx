import type { CSSProperties } from "react";
import { prefersReducedMotion, useMediaQuery } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { Chip, GuideMark } from "./parts";

/**
 * The interests as a living constellation: chips on two slow orbits around a maroon sun (the
 * student). Hovering or focusing pauses the orbits so a chip can be removed. Narrow screens and
 * reduced motion get a still, wrapped list instead.
 */
export function Constellation({ items, onRemove, center }: { items: string[]; onRemove: (item: string) => void; center: string }) {
  const wide = useMediaQuery("(min-width: 640px)");
  const still = !wide || prefersReducedMotion() || items.length === 0;
  if (still) {
    return (
      <ul className="flex flex-wrap gap-2" aria-label="Interests">
        {items.map((item) => (
          <li key={item}>
            <Chip label={item} onRemove={() => onRemove(item)} />
          </li>
        ))}
      </ul>
    );
  }
  // Up to five on one ring; more go on a second, wider ring turning the other way.
  const inner = items.length <= 5 ? items : items.slice(0, 5);
  const outer = items.slice(inner.length);
  const rings: { items: string[]; size: number; seconds: number; reverse: boolean }[] = [
    { items: inner, size: outer.length ? 290 : 310, seconds: 160, reverse: false },
    { items: outer, size: 470, seconds: 220, reverse: true },
  ];
  const height = outer.length ? 520 : 380;
  return (
    <div className="dash-constellation relative mx-auto w-full max-w-[640px] overflow-hidden" style={{ height }}>
      <div role="list" aria-label="Interests" className="absolute inset-0">
        {rings.map((ring, r) =>
          ring.items.length === 0 ? null : (
            <div
              key={r}
              className="dash-orbit"
              data-reverse={ring.reverse}
              style={{ width: ring.size, height: ring.size, "--orbit-s": `${ring.seconds}s` } as CSSProperties}
            >
              {ring.items.map((item, i) => {
                const angle = (360 / ring.items.length) * i + r * 24;
                return (
                  <div role="listitem" key={item} className="dash-orbit-item" style={{ "--a": `${angle}deg`, "--r": `${ring.size / 2}px` } as CSSProperties}>
                    <span className="dash-orbit-upright">
                      <Chip label={item} onRemove={() => onRemove(item)} className="bg-surface-card shadow-hover" />
                    </span>
                  </div>
                );
              })}
            </div>
          ),
        )}
      </div>
      <div aria-hidden="true" className={cn("dash-sun absolute left-1/2 top-1/2 flex size-24 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-pill bg-primary text-center text-on-primary")}>
        <GuideMark size={16} />
        <span className="mt-1 max-w-[5.5rem] truncate font-display text-[15px] italic leading-tight">{center}</span>
      </div>
    </div>
  );
}
