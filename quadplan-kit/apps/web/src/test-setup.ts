import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { resetMockState } from "./mocks/handlers";
import { server } from "./mocks/node";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetMockState();
  try {
    window.localStorage.clear();
  } catch {
    // ignore
  }
});
afterAll(() => server.close());
