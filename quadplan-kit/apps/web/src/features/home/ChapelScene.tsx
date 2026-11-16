import { useEffect, type CSSProperties } from "react";
import type {} from "./ascii-scene";

const SCRIPT = "/ascii-scene/ascii-scene.js";

/** Loads the scene's module once, when the browser is idle, so it never delays the page. */
let loading: Promise<unknown> | null = null;
function loadScene(): void {
  // jsdom (unit tests) and very old browsers lack what the scene needs: show nothing.
  if (
    loading ||
    typeof ResizeObserver === "undefined" ||
    typeof FontFace === "undefined" ||
    !window.customElements
  )
    return;
  loading = import(/* @vite-ignore */ SCRIPT).catch(() => {
    loading = null;
  });
}

// The scene sits straight on the page canvas (no box): DESIGN.md tokens, muted a little so the
// sandstone and greens sit with the page's neutral type and maroon accent.
const sceneStyle = {
  "--ascii-paper": "var(--color-canvas)",
  "--ascii-ink": "var(--color-ink)",
  "--ascii-ink-mix": "0.14",
  "--ascii-saturation": "0.85",
} as CSSProperties;

/**
 * The homepage's animated ASCII drawing of Rockefeller Chapel (FEEDBACK "ASCII Scene",
 * 2026-11-16). Sky, light and weather follow the real time and weather in Hyde Park (weather from
 * our own `/api/weather`, so no request leaves the site; Open-Meteo is credited on /about). Sweeping the pointer across the trees
 * makes them sway; a click sends a shooting star down the night sky, or birds up by day. Still
 * under reduced motion. The drawing is decorative; the page works without it.
 */
export function ChapelScene() {
  useEffect(() => {
    const w = window as Window & {
      requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (w.requestIdleCallback) {
      const id = w.requestIdleCallback(loadScene, { timeout: 1500 });
      return () => w.cancelIdleCallback?.(id);
    }
    const id = window.setTimeout(loadScene, 300);
    return () => window.clearTimeout(id);
  }, []);
  return (
    <div className="home-scene w-full">
      <ascii-scene
        src="/ascii-scene/scene.rockefeller.json"
        weather-src="/api/weather"
        fade="0.18"
        density="4.6"
        label="Animated drawing of Rockefeller Chapel in characters, following the time of day and the weather in Hyde Park"
        style={sceneStyle}
      />
    </div>
  );
}
