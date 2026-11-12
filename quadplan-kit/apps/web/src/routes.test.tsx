import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./routes";

const CASES: [string, string][] = [
  ["/", "Quarterly"],
  ["/plan", "Planner"],
  ["/courses/MATH%2020700", "Course"],
  ["/courses/MATH%2020700/i/jane-doe/t/1", "Thread"],
  ["/admin/review", "Curator console"],
  ["/nope", "Page not found"],
];

describe("routes", () => {
  it.each(CASES)("renders %s", async (path, heading) => {
    const router = createMemoryRouter(routes, { initialEntries: [path] });
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });
});
