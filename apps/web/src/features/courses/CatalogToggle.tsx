import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import "./glass.css";

type Kind = "courses" | "programs";

const ITEMS: { key: Kind; to: string; label: string }[] = [
  { key: "courses", to: "/courses", label: "Courses" },
  { key: "programs", to: "/programs", label: "Programs" },
];

/** The side shown last, so the pill can slide from it when the other page mounts. */
let lastShown: Kind | null = null;

/**
 * Courses and programs share one menu item, "Catalog"; this switch moves between them
 * (FEEDBACK "Course Search and Programs GUI", 2026-11-16).
 *
 * A small segmented control (D5, FEEDBACK "Minor design changes"): a light track, the current side
 * on a white pill in maroon. Switching slides the pill from the side you left (200ms ease-out;
 * still under reduced motion). Each link is drawn 32px tall but keeps a 44px target.
 */
export function CatalogToggle({ current }: { current: Kind }) {
  const refs = useRef<Record<Kind, HTMLAnchorElement | null>>({ courses: null, programs: null });
  const from = useRef<Kind>(lastShown ?? current);
  const [at, setAt] = useState<{ x: number; w: number; animate: boolean } | null>(null);

  useLayoutEffect(() => {
    const measure = (k: Kind, animate: boolean) => {
      const el = refs.current[k];
      if (el) setAt({ x: el.offsetLeft, w: el.offsetWidth, animate });
    };
    // Start where the previous page left the pill, then move it on the next frame.
    measure(from.current, false);
    const id = requestAnimationFrame(() => measure(current, true));
    lastShown = current;
    from.current = current;
    const remeasure = () => measure(current, false);
    window.addEventListener("resize", remeasure);
    void document.fonts?.ready.then(remeasure);
    return () => {
      cancelAnimationFrame(id);
      window.removeEventListener("resize", remeasure);
    };
  }, [current]);

  // Keep the module-level memory in step if this page unmounts before the frame above runs.
  useEffect(() => () => void (lastShown = current), [current]);

  return (
    <nav aria-label="Courses or programs" className="qg-seg">
      {at && (
        <span
          aria-hidden="true"
          className={cn(
            // Dark glass: a lit glass thumb in a recessed track. The segments share one width, so
            // only the transform moves (a long, soft ease).
            "qg-seg-thumb",
            at.animate && "transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none",
          )}
          style={{ transform: `translateX(${at.x}px)`, width: at.w }}
        />
      )}
      {ITEMS.map(({ key, to, label }) => (
        <Link
          key={key}
          ref={(el) => void (refs.current[key] = el)}
          to={to}
          aria-current={current === key ? "page" : undefined}
          className={cn(
            // 38px drawn, 44px to tap: the ::after strip extends the target above and below.
            "relative z-10 inline-flex h-[38px] w-[7.5rem] items-center justify-center gap-2 rounded-pill text-body-sm font-medium transition-colors duration-300",
            "after:absolute after:inset-x-0 after:-inset-y-1 after:content-['']",
            current === key ? "text-ink" : "text-muted hover:text-ink",
          )}
        >
          {current === key && <span aria-hidden="true" className="qg-dot" />}
          {label}
        </Link>
      ))}
    </nav>
  );
}
