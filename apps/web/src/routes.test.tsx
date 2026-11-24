import { screen, waitFor } from "@testing-library/react";
import { renderRoute } from "./test-utils";

const CASES: [string, string][] = [
  ["/", "The Best of UChicago, within your reach."],
  ["/plan", "Planner"],
  ["/onboarding", "Planner setup"],
  ["/courses", "Catalog"],
  ["/courses/TEST%2010000", "TEST 10000 · Fake Introduction I"],
  ["/programs", "Program explorer"],
  ["/programs/fake-major", "Fake Program"],
  ["/courses/MATH%2020700/i/jane-doe/t/1", "Thread"],
  ["/admin/review", "Curator console"],
  ["/nope", "Page not found"],
];

describe("routes", () => {
  it.each(CASES)("renders %s", async (path, heading) => {
    renderRoute(path);
    // Retried until it holds: forum pages swap their "checking your login" header for the real one.
    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: heading })).toBeInTheDocument());
  });
});

describe("top nav", () => {
  it("has four tabs in order: Dashboard, Planner, Catalog, Forum (issue #15)", async () => {
    renderRoute("/courses");
    const nav = await screen.findByRole("navigation", { name: "Main" });
    const links = [...nav.querySelectorAll("a")].map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([
      ["Dashboard", "/me"],
      ["Planner", "/plan"],
      ["Catalog", "/courses"],
      ["Forum", "/forum"],
    ]);
  });

  it("sends the old Ask page to the planner (issue #15)", async () => {
    const { router } = renderRoute("/ask?q=hello");
    await waitFor(() => expect(router.state.location.pathname).toBe("/plan"));
  });

  it.each([
    ["/plans", "Planner"],
    ["/onboarding", "Planner"],
    ["/courses/TEST%2010000", "Catalog"],
    ["/programs", "Catalog"], // courses and programs share one item (FEEDBACK 2026-11-16)
    ["/courses/TEST%2010000/i/fake-instructor-a", "Forum"],
    ["/guidelines", "Forum"],
  ])("marks the section of %s as current", async (path, label) => {
    renderRoute(path);
    const nav = await screen.findByRole("navigation", { name: "Main" });
    const current = nav.querySelectorAll('[aria-current="page"]');
    expect([...current].map((a) => a.textContent)).toEqual([label]);
  });
});
