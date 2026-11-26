import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test-utils";

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
    const planner = await screen.findByRole("heading", { name: "Planner", level: 2 });
    expect(planner).toBeInTheDocument();
    expect(await screen.findByText(/The planner is not available yet/)).toBeInTheDocument();
    expect(screen.getByText(/Answers are written by an AI/)).toBeInTheDocument();
  });

  it("falls back to the current academic year when catalog years are unavailable", async () => {
    renderRoute("/plan");
    expect(await screen.findByText(/^Catalog \d{4}-\d{2}$/)).toBeInTheDocument();
  });
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
