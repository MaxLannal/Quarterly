import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
// One font, bundled from npm (no CDN; nothing leaves the site's origin): Figtree, a smooth geometric
// sans, for every heading, label and paragraph (docs/DESIGN.md "Simple light", Max 2026-11-27).
import "@fontsource-variable/figtree";
import "./index.css";
import { routes } from "./routes";

async function main() {
  // Mock the API only in builds made with VITE_MOCK_API=1 (e2e, mock-mode dev).
  if (import.meta.env.VITE_MOCK_API === "1") {
    const { startMockWorker } = await import("./mocks/browser");
    await startMockWorker();
  }

  const queryClient = new QueryClient();
  const router = createBrowserRouter(routes);

  const root = document.getElementById("root");
  if (!root) throw new Error("#root element missing");

  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  );
}

void main();
