import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Day or night on the homepage (Max, 2026-11-20). The scene is painted entirely in the chapel's
 * course titles (chapel/renderer.ts): at night the sky's titles turn a deep blue with a few starry
 * letters and a moon, snow falls as bright letters drifting down, the lawn is under snow, and the
 * two street lamps (drawn in titles by day as well) glow orange and warm the snow below them.
 */

export type Scene = "day" | "night";
const KEY = "quarterly.home.scene";

export function useScene(): [Scene, (s: Scene) => void] {
  const [scene, setScene] = useState<Scene>(() => {
    try {
      return window.localStorage.getItem(KEY) === "night" ? "night" : "day";
    } catch {
      return "day";
    }
  });
  const set = (s: Scene) => {
    setScene(s);
    try {
      window.localStorage.setItem(KEY, s);
    } catch {
      // storage blocked: the choice lasts for this visit
    }
  };
  return [scene, set];
}

/** The Day / Night switch: a small segmented pill at the top right of the hero. */
export function SceneSwitch({ scene, onChange }: { scene: Scene; onChange: (s: Scene) => void }) {
  const night = scene === "night";
  const ref = useRef<HTMLDivElement>(null);
  // The chapel behind listens for the pointer on the whole hero: over the switch it names no course.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const stop = (e: Event) => e.stopPropagation();
    el.addEventListener("pointermove", stop);
    el.addEventListener("pointerdown", stop);
    return () => {
      el.removeEventListener("pointermove", stop);
      el.removeEventListener("pointerdown", stop);
    };
  }, []);
  return (
    <div
      ref={ref}
      role="radiogroup"
      aria-label="Homepage scene"
      className={cn(
        "flex items-center gap-1 rounded-pill border p-1 backdrop-blur-md transition-colors duration-700",
        night
          ? "border-[rgb(255_200_140/0.35)] bg-[rgb(14_19_48/0.92)] shadow-overlay"
          : "border-hairline bg-surface-card/90 shadow-hover",
      )}
    >
      {(["day", "night"] as const).map((s) => {
        const on = scene === s;
        return (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(s)}
            className={cn(
              "inline-flex min-h-11 items-center gap-2 rounded-pill px-4 text-button transition-colors duration-500",
              on
                ? night
                  ? "bg-[#ffb35c] text-[#141b3a]"
                  : "bg-primary text-on-primary"
                : night
                  ? "text-on-night/80 hover:bg-on-night/15"
                  : "text-body-strong hover:bg-surface-strong",
            )}
          >
            {s === "day" ? <SunGlyph /> : <MoonGlyph />}
            {s === "day" ? "Day" : "Night"}
          </button>
        );
      })}
    </div>
  );
}

function SunGlyph() {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" />
    </svg>
  );
}

function MoonGlyph() {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
      <path d="M19.5 14.6A8 8 0 0 1 9.4 4.5a8 8 0 1 0 10.1 10.1z" />
    </svg>
  );
}
