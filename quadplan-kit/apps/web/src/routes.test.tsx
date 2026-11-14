import { screen } from "@testing-library/react";
import { renderRoute } from "./test-utils";

const CASES: [string, string][] = [
  ["/", "Quarterly"],
  ["/plan", "Planner"],
  ["/onboarding", "Planner setup"],
  ["/courses", "Course search"],
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
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });
});

describe("top nav", () => {
  it.each([
    ["/plans", "Plan"],
    ["/onboarding", "Plan"],
    ["/courses/TEST%2010000", "Courses"],
    ["/courses/TEST%2010000/i/fake-instructor-a", "Forum"],
    ["/guidelines", "Forum"],
  ])("marks the section of %s as current", async (path, label) => {
    renderRoute(path);
    const nav = await screen.findByRole("navigation", { name: "Main" });
    const current = nav.querySelectorAll('[aria-current="page"]');
    expect([...current].map((a) => a.textContent)).toEqual([label]);
  });
});
