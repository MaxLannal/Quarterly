import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/**
 * Starts MSW in the browser (VITE_MOCK_API=1 builds only: e2e and mock-mode dev).
 *
 * Tests that answer `/api/*` themselves (`page.route`, e.g. e2e/auth.spec.ts) run with
 * Playwright's `serviceWorkers: "block"`, because requests answered by a service worker never
 * reach `page.route`. Registration then fails; the app starts without mocks instead of not at all.
 */
export async function startMockWorker(): Promise<void> {
  const worker = setupWorker(...handlers);
  try {
    await worker.start({ onUnhandledFrame: "bypass", quiet: true });
  } catch {
    console.warn("[mocks] service worker not registered; API calls are not mocked");
  }
}
