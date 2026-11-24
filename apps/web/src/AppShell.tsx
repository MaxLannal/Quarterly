import { Outlet } from "react-router-dom";
import { Footer } from "@/components/layout/Footer";
import { TopNav } from "@/components/layout/TopNav";
import { Notice } from "@/components/ui/misc";
import { useImportOnLogin } from "@/features/planner/importOnLogin";

export function AppShell() {
  const importStatus = useImportOnLogin();
  return (
    // The night behind everything (body background, index.css); the page is a white sheet on it
    // (docs/DESIGN.md "Maroon and night", after the reference login card).
    <div className="flex min-h-screen flex-col text-ink">
      <a
        href="#main"
        className="sr-only rounded-pill bg-surface-card px-4 py-2 text-nav-link text-ink shadow-overlay focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50"
      >
        Skip to content
      </a>
      <TopNav />
      <main
        id="main"
        className="page-sheet mx-2 flex-1 overflow-clip rounded-[28px] bg-canvas shadow-sheet sm:mx-3 sm:rounded-sheet lg:mx-5"
      >
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
  );
}
