import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { resetSession } from "./features/auth/session";
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
  resetSession(); // the login state is module-wide: start every test logged out and unloaded
  try {
    window.localStorage.clear();
  } catch {
    // ignore
  }
});
afterAll(() => server.close());
