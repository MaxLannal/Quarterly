import { useEffect, useRef, useState, type CSSProperties } from "react";
import { hash } from "./art/rng";
import { useReducedMotion, useVisibleWords } from "./hooks";

const MAX_WORDS = 30;
const DEPTHS = [
  { size: "text-[15px]", alpha: 0.16, duration: 52, parallax: 0.015 },
  { size: "text-[24px]", alpha: 0.2, duration: 38, parallax: 0.045 },
  { size: "text-[40px]", alpha: 0.13, duration: 27, parallax: 0.09 },
] as const;

/**
 * The words of the cards on screen drift slowly upward behind the feed, at three depths, with a
 * little parallax as the page scrolls. Purely decorative (pointer-events none, hidden from
 * assistive technology); not drawn at all under reduced motion.
 */
export function FloatingWords() {
  const reduced = useReducedMotion();
  const live = useVisibleWords();
  const [words, setWords] = useState<readonly string[]>([]);
  const layers = useRef<(HTMLDivElement | null)[]>([]);

  // Follow the visible words calmly, not on every scroll step.
  useEffect(() => {
    const t = window.setTimeout(() => setWords(live.slice(0, MAX_WORDS)), 500);
    return () => window.clearTimeout(t);
  }, [live]);

  useEffect(() => {
    if (reduced) return;
    let frame = 0;
    const apply = () => {
      frame = 0;
      const y = window.scrollY;
      layers.current.forEach((el, i) => {
        if (el) el.style.transform = `translate3d(0, ${(-y * DEPTHS[i]!.parallax).toFixed(1)}px, 0)`;
      });
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(apply);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    apply();
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [reduced]);

  if (reduced) return null;
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {DEPTHS.map((depth, d) => (
        <div
          key={d}
          ref={(el) => {
            layers.current[d] = el;
          }}
          className="absolute inset-0 will-change-transform"
        >
          {words.map((word, i) => {
            const h = hash(word);
            if (h % 3 !== d) return null;
            const style = {
              left: `${(h % 92) + 2}%`,
              "--duration": `${depth.duration + (h % 11)}s`,
              "--delay": `${-((h >>> 4) % (depth.duration * 10)) / 10}s`,
              "--alpha": depth.alpha,
              "--sway": `${((h >>> 8) % 60) - 30}px`,
            } as CSSProperties;
            return (
              <span
                key={word}
                style={style}
                className={`feed-float-word font-display italic ${depth.size} ${i % 4 === 0 ? "text-primary" : "text-ink"}`}
              >
                {word}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}
