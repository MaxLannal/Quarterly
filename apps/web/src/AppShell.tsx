import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Aurora } from "@/components/brand/Aurora";
import { Footer } from "@/components/layout/Footer";
import { TopNav } from "@/components/layout/TopNav";
import { Notice } from "@/components/ui/misc";
import { useImportOnLogin } from "@/features/planner/importOnLogin";

/** Pages that sit straight on the night, with the light at full strength and no pane of glass. */
const BARE_PAGES = new Set(["/"]);
/** Pages whose own glass card floats on the night at full light (docs/DESIGN.md "Dark glass"). */
const BRIGHT_PAGES = new Set(["/", "/login", "/signup"]);

/**
 * One listener for the whole app: the red light under the pointer on any [data-spotlight] surface
 * (index.css). It only writes two CSS variables on the surface being hovered.
 */
function useSpotlight() {
  useEffect(() => {
    if (window.matchMedia?.("(pointer: coarse)").matches) return;
    let frame = 0;
    let last: PointerEvent | null = null;
    const paint = () => {
      frame = 0;
      const e = last;
      if (!e || !(e.target instanceof Element)) return;
      const el = e.target.closest<HTMLElement>("[data-spotlight]");
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--spot-x", `${e.clientX - r.left}px`);
      el.style.setProperty("--spot-y", `${e.clientY - r.top}px`);
    };
    const onMove = (e: PointerEvent) => {
      last = e;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      document.removeEventListener("pointermove", onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
}

export function AppShell() {
  const importStatus = useImportOnLogin();
  const { pathname } = useLocation();
  useSpotlight();
  return (
    // The night and its light behind everything (Aurora); each page is a pane of smoked glass on it
    // (docs/DESIGN.md "Dark glass").
    <div className="flex min-h-screen flex-col text-ink">
      <Aurora intensity={BRIGHT_PAGES.has(pathname) ? "bright" : "dim"} />
      <a
        href="#main"
        className="sr-only rounded-pill bg-surface-raised px-4 py-2 text-nav-link text-ink shadow-overlay focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50"
      >
        Skip to content
      </a>
      <TopNav />
      <main
        id="main"
        data-bare={BARE_PAGES.has(pathname) ? "true" : undefined}
        className="page-sheet mx-2 flex-1 overflow-clip rounded-[28px] shadow-sheet sm:mx-3 sm:rounded-sheet lg:mx-5"
      >
        {importStatus === "imported" && (
          <div className="mx-auto w-full max-w-tool px-4 pt-5 sm:px-6 lg:px-8">
            <Notice tone="success" role="status">
              Your plans from this device were added to your account.
            </Notice>
          </div>
        )}
        <div key={pathname} className="page-enter">
          <Outlet />
        </div>
      </main>
      <Footer />
    </div>
  );
}
