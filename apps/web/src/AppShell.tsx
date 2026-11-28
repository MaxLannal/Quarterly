import { Outlet } from "react-router-dom";
import { Footer } from "@/components/layout/Footer";
import { Sidebar, TopBar, useSidebar } from "@/components/layout/TopNav";
import { Notice } from "@/components/ui/misc";
import { useImportOnLogin } from "@/features/planner/importOnLogin";

/**
 * "Simple light" (docs/DESIGN.md, Max 2026-11-27, after his reference dashboard): the sidebar on a
 * light grey frame, and each page in one white panel with soft corners beside it.
 */
export function AppShell() {
  const importStatus = useImportOnLogin();
  const sidebar = useSidebar();
  return (
    <div className="min-h-screen text-ink lg:grid lg:grid-cols-[272px_minmax(0,1fr)]">
      <a
        href="#main"
        className="sr-only rounded-lg bg-canvas px-4 py-2 text-nav-link text-ink shadow-overlay focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60]"
      >
        Skip to content
      </a>
      <Sidebar open={sidebar.open} onClose={() => sidebar.setOpen(false)} id={sidebar.id} />
      <div className="flex min-w-0 flex-col lg:py-3 lg:pr-3">
        <div className="flex min-h-screen flex-col bg-canvas lg:min-h-[calc(100vh-24px)] lg:rounded-sheet lg:border lg:border-hairline">
          <TopBar menuOpen={sidebar.open} onMenu={() => sidebar.setOpen(!sidebar.open)} menuId={sidebar.id} />
          <main id="main" className="flex-1">
            {importStatus === "imported" && (
              <div className="mx-auto w-full max-w-tool px-4 pt-5 sm:px-6 lg:px-8">
                <Notice tone="success" role="status">
                  Your plans from this device were added to your account.
                </Notice>
              </div>
            )}
            <Outlet />
          </main>
          <Footer />
        </div>
      </div>
    </div>
  );
}
