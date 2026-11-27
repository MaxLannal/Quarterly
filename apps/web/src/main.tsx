import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
// Fonts are bundled from npm (no CDN, nothing leaves the site's origin): Inter for body and UI,
// Instrument Serif for headlines and the wordmark, JetBrains Mono for small labels, Newsreader for
// voices and quotes (docs/DESIGN.md "Dark glass").
import "@fontsource-variable/inter";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource/newsreader/300.css";
import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/500.css";
import "@fontsource/newsreader/400-italic.css";
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
