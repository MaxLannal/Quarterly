import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { prefersReducedMotion } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { loadCourseTitles, TypeScapeEngine } from "./typescape/engine";
import type { ShapeName } from "./typescape/shapes";

export type { ShapeName };

function canRun(): boolean {
  // jsdom (unit tests) has no canvas: show nothing.
  return (
    typeof ResizeObserver !== "undefined" &&
    typeof IntersectionObserver !== "undefined" &&
    typeof HTMLCanvasElement !== "undefined" &&
    !/jsdom/i.test(navigator.userAgent)
  );
}

/**
 * A figure drawn with the titles of real courses (docs/BEST-OF-UCHICAGO-PLAN.md "Shared look"),
 * in the homepage chapel's manner: maroon and ink on paper, rows like courses of stone. `shape`:
 * `arch` (a Gothic window, Ask), `orbit` (rings around a sun, the dashboard), `river` (flowing
 * bands, the feed), `arcade` (a cloister, the forum). Point at a title to see its course; click
 * to open it. Decorative: the page's own links and buttons do everything it does.
 */
export function TypeScape({
  shape,
  focus = 0.72,
  words = [],
  label,
  className,
  theme = "paper",
  zoom = 1,
}: {
  shape: ShapeName;
  /** Horizontal centre of the figure (0..1) on wide screens; narrow screens centre it. */
  focus?: number;
  /** Words woven into the titles, drawn heavier (e.g. the student's interests). */
  words?: string[];
  label: string;
  className?: string;
  /** "night": light titles for a GradientArt panel (the redesign's split heroes). */
  theme?: "paper" | "night";
  /** How large the figure is drawn in its canvas (about 1.5 in a panel). */
  zoom?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);
  const navigate = useNavigate();
  const wordKey = words.join("\u0001");

  useEffect(() => {
    const canvas = canvasRef.current;
    const tip = labelRef.current;
    if (!canvas || !tip || !canRun()) return;
    let engine: TypeScapeEngine | null = null;
    let cancelled = false;
    const fonts = "fonts" in document ? document.fonts.load('500 12px "Newsreader"') : null;
    Promise.all([loadCourseTitles(), fonts?.catch(() => undefined)]).then(([titles]) => {
      if (cancelled) return;
      try {
        engine = new TypeScapeEngine(canvas, tip, titles, {
          shape,
          focus,
          words: wordKey ? wordKey.split("\u0001") : [],
          reducedMotion: prefersReducedMotion(),
          onOpen: (code) => navigate(`/courses/${encodeURIComponent(code)}`),
          theme,
          zoom,
        });
        engine.loop();
        canvas.dataset.state = "running";
      } catch {
        canvas.dataset.state = "failed";
      }
    });
    return () => {
      cancelled = true;
      engine?.dispose();
    };
  }, [shape, focus, wordKey, navigate, theme, zoom]);

  return (
    <div className={cn("pointer-events-none absolute inset-0 -z-10", className)}>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={label}
        data-shape={shape}
        className="typescape pointer-events-auto size-full"
      />
      <span
        ref={labelRef}
        aria-hidden="true"
        data-visible="false"
        className="course-chapel-label pointer-events-none absolute left-0 top-0 z-20 max-w-[min(26rem,calc(100%-1rem))] truncate rounded-pill bg-surface-card px-3 py-1 text-caption text-body shadow-overlay [&>strong]:text-ink"
      />
    </div>
  );
}
