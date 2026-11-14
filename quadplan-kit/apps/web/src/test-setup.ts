import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { resetMockState } from "./mocks/handlers";
import { server } from "./mocks/node";

// The default 1 s for findBy*/waitFor is too short when `make check` runs every suite at once
// on a busy machine; a real failure still fails, only later.
configure({ asyncUtilTimeout: 5000 });

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
