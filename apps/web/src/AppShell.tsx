import { Outlet } from "react-router-dom";
import { Footer } from "@/components/layout/Footer";
import { TopNav } from "@/components/layout/TopNav";
import { Notice } from "@/components/ui/misc";
import { Companion } from "@/features/companion/Companion";
import { useImportOnLogin } from "@/features/planner/importOnLogin";

export function AppShell() {
  const importStatus = useImportOnLogin();
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-ink">
      <a
        href="#main"
        className="sr-only rounded-pill bg-surface-card px-4 py-2 text-nav-link text-ink shadow-overlay focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50"
      >
        Skip to content
      </a>
      <TopNav />
      {importStatus === "imported" && (
        <div className="mx-auto w-full max-w-tool px-4 pt-4 sm:px-6 lg:px-8">
          <Notice tone="success" role="status">
            Your plans from this device were added to your account.
          </Notice>
        </div>
      )}
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <Footer />
      <Companion />
    </div>
  );
}
