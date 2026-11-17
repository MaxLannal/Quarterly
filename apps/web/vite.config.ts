import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { msw } from "msw/vite";
import { defineConfig } from "vite";

// VITE_MOCK_API=1 serves (dev) or emits (build) the MSW worker script; the Docker build omits it.
const mockApi = process.env.VITE_MOCK_API === "1";

export default defineConfig({
  plugins: [react(), tailwindcss(), ...(mockApi ? [msw({ mode: "worker-only" })] : [])],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
