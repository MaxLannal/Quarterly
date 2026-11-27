import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { StrictMode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { sse } from "@/mocks/agents";
import { server } from "@/mocks/node";
import { routes } from "@/routes";
import { newQueryClient, renderRoute } from "@/test-utils";

const notBuilt = () => HttpResponse.json({ detail: "Not implemented yet" }, { status: 501 });

describe("Planner with endpoints that are not built yet (501)", () => {
  beforeEach(() => {
    server.use(
      http.post("*/api/verify", notBuilt),
      http.post("*/api/agents/planner", notBuilt),
      http.get("*/api/catalog-years", notBuilt),
    );
  });

  it("shows clear 'not available yet' states instead of breaking", async () => {
    const user = userEvent.setup();
    renderRoute("/plan");
    expect(await screen.findByText("Verifier not available yet")).toBeInTheDocument();
    expect(screen.getByText(/The verifier is not available yet/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Generate plan" }));
    const planner = await screen.findByRole("heading", { name: "Ask Quarterly", level: 2 });
    expect(planner).toBeInTheDocument();
    expect(await screen.findByText(/The planner is not available yet/)).toBeInTheDocument();
    expect(screen.getByText(/Answers are written by an AI/)).toBeInTheDocument();
  });

  it("falls back to the current academic year when catalog years are unavailable", async () => {
    renderRoute("/plan");
    expect(await screen.findByText(/^Catalog \d{4}-\d{2}$/)).toBeInTheDocument();
  });
});

describe("Planner opened with ?generate=1", () => {
  it("starts one generation, also under StrictMode, and drops the parameter so a reload does not start another", async () => {
    // Live (2026-11-26): StrictMode ran the mount effect twice (two paid runs), and the
    // parameter stayed in the address, so every reload started one more.
    let calls = 0;
    server.use(
      http.post("*/api/agents/planner", () => {
        calls += 1;
        return new HttpResponse("", { headers: { "Content-Type": "text/event-stream" } });
      }),
    );
    const router = createMemoryRouter(routes, { initialEntries: ["/plan?generate=1"] });
    render(
      <StrictMode>
        <QueryClientProvider client={newQueryClient()}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </StrictMode>,
    );
    await screen.findByRole("heading", { name: "Ask Quarterly", level: 2 });
    await waitFor(() => expect(router.state.location.search).toBe(""));
    await waitFor(() => expect(calls).toBe(1));
    await new Promise((r) => setTimeout(r, 50));
    expect(calls).toBe(1);
  }, 15_000);
});

describe("Planner and the math placement", () => {
  it("adds the placement the student gave the planner to the plan's credits, once", async () => {
    // The run planned with this placement; the page's plan needs it too, or the proposals
    // would not fit it (and the plan check would not count the placement).
    server.use(http.post("*/api/agents/planner", () => sse([{ type: "done", run_id: "r1", placements: ["MATH 15100"] }])));
    const user = userEvent.setup();
    renderRoute("/plan");
    await user.click(await screen.findByRole("button", { name: "Generate plan" }));
    const placement = { kind: "placement", label: "MATH 15100", maps_to: null, units: 0 };
    const credits = () => (JSON.parse(localStorage.getItem("quarterly.plans.v1") ?? "{}") as { plans?: { state: { credits?: unknown[] } }[] }).plans?.[0]?.state.credits;
    await waitFor(() => expect(credits()).toEqual([placement]));
    await user.click(screen.getByRole("button", { name: "Generate plan" }));
    await new Promise((r) => setTimeout(r, 100));
    expect(credits()).toEqual([placement]);
  }, 15_000);
});

describe("Planner with mocks", () => {
  it("adds a program and shows requirement progress from the verifier", async () => {
    const user = userEvent.setup();
    renderRoute("/plan");
    await user.click(await screen.findByRole("button", { name: "+ Program" }));
    const dialog = screen.getByRole("dialog", { name: "Programs" });
    await user.click(await within(dialog).findByRole("checkbox", { name: /Fake Minor/ }));
    expect(within(dialog).getByText("Not yet hand-checked")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Save programs" }));
    await user.click(screen.getByRole("button", { name: "Requirements" }));
    const node = await screen.findByRole("button", { name: /^Fake theory part/ });
    await waitFor(() => expect(node).toHaveTextContent("0 of 1 courses"));
    // Errors stay subtle: a small count on "Check plan", the list inside the panel.
    expect(await screen.findByRole("button", { name: "Check plan (1 error)" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Check plan (1 error)" }));
    expect(await within(screen.getByTestId("plan-drawer")).findByText("1 error")).toBeInTheDocument();
    // PL-1 (D11): the verdict also sits beside the plan's name, and opens the plan check.
    expect(screen.getByTestId("plan-verdict")).toHaveTextContent("1 error");
  });
});
