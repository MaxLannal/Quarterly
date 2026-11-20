import { type RefObject, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { prefersReducedMotion } from "@/lib/motion";
import { ChapelController } from "./chapel/controller";

function canRun(): boolean {
  // jsdom (unit tests) and very old browsers lack what the picture needs: show nothing.
  return (
    typeof ResizeObserver !== "undefined" &&
    typeof IntersectionObserver !== "undefined" &&
    typeof document !== "undefined" &&
    "fonts" in document &&
    typeof HTMLCanvasElement !== "undefined" &&
    !/jsdom/i.test(navigator.userAgent)
  );
}

/**
 * The homepage's hero picture: Rockefeller Chapel filling the screen, drawn with the titles of
 * real courses from the catalog, set in rows like courses of stone, in maroon, black and white.
 * Letters have depth (the lawn comes towards you, the sky stays far) and the picture shifts with
 * the pointer. The light changes on its own: clouds drift across the sky and their shadows cross
 * the chapel, and sunlight moves slowly over the stone. A mouse or a finger lifts and magnifies
 * the letters under it like a glass; the title under the mouse turns ink and a label shows its
 * code and full title, and a click opens that course. Under reduced motion, or without a GPU, it
 * is a still picture (the label and the click still work). The picture is decorative; search and
 * the buttons do everything it does.
 */
export function CourseChapel({
  sectionRef,
  uiRef,
}: {
  sectionRef: RefObject<HTMLElement | null>;
  uiRef: RefObject<HTMLElement | null>;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const section = sectionRef.current;
    const ui = uiRef.current;
    const canvas = canvasRef.current;
    const label = labelRef.current;
    if (!section || !ui || !canvas || !label || !canRun()) return;
    const controller = new ChapelController(
      { section, canvas, label, ui },
      (code) => navigate(`/courses/${encodeURIComponent(code)}`),
      prefersReducedMotion(),
    );
    (canvas as HTMLCanvasElement & { chapel?: ChapelController }).chapel = controller;
    // start straight away: the page is already drawn, and the picture is the first thing to see
    controller.init().catch(() => {
      canvas.dataset.state = "failed";
    });
    return () => controller.dispose();
  }, [sectionRef, uiRef, navigate]);

  return (
    <>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label="Rockefeller Chapel, drawn with the titles of courses in the 2026-27 College Catalog"
        className="course-chapel absolute inset-0 -z-10 size-full"
      />
      <span
        ref={labelRef}
        aria-hidden="true"
        data-visible="false"
        className="course-chapel-label pointer-events-none absolute left-0 top-0 z-20 max-w-[min(26rem,calc(100%-1rem))] truncate rounded-pill bg-surface-card px-3 py-1 text-caption text-body shadow-overlay [&>strong]:text-ink"
      />
    </>
  );
}
