import { defineConfig, devices } from "@playwright/test";

// Journeys A-D (SPEC "Core user journeys") against the real Docker stack: seed data, the
// request-driven fake LLM (LLM_FAKE=e2e) and console email. Started by `make e2e-stack`,
// which brings the stack up with docker-compose.e2e.yml and seeds it. No webServer: the
// stack's web service (nginx + the real API) is the server.
export default defineConfig({
  testDir: "./e2e-stack",
  globalSetup: "./e2e-stack/global-setup.ts",
  globalTeardown: "./e2e-stack/global-teardown.ts",
    // One database for every test: run them one at a time.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.STACK_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    viewport: { width: 1440, height: 1000 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } }],
});
