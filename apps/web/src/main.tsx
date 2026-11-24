import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
// Fonts are bundled from npm (no CDN): Inter for body/UI, Newsreader 300 for display.
import "@fontsource-variable/inter";
import "@fontsource/newsreader/300.css";
// 400: the home wordmark (D2); 500: the top-bar wordmark (D4). FEEDBACK "Minor design changes".
import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/500.css";
// 400 italic: the maroon accent words of the headlines (TypeHero, the homepage title).
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
