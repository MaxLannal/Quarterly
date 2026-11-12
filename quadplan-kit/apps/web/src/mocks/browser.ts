import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/** Starts MSW in the browser (VITE_MOCK_API=1 builds only: e2e and mock-mode dev). */
export async function startMockWorker(): Promise<void> {
  const worker = setupWorker(...handlers);
  await worker.start({ onUnhandledFrame: "bypass", quiet: true });
}
