import { defineConfig, devices } from "@playwright/test";

// Each worktree/agent can pick its own port with E2E_PORT to avoid collisions.
const port = Number(process.env.E2E_PORT ?? 4173);
const outDir = port === 4173 ? "dist" : `dist-e2e-${port}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${port}`, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // e2e runs against MSW mocks (VITE_MOCK_API=1); the Docker build calls the real API. Each port
    // builds into its own folder, so runs on different ports never overwrite each other's build.
    command: `VITE_MOCK_API=1 npx vite build --outDir ${outDir} --emptyOutDir && npx vite preview --outDir ${outDir} --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
