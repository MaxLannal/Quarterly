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
      http.post("*/api/agents/generate", notBuilt),
      http.post("*/api/plans/generate", notBuilt),
      http.post("*/api/agents/chat", notBuilt),
      http.get("*/api/catalog-years", notBuilt),
    );
  });

  it("shows clear 'not available yet' states instead of breaking", async () => {
    const user = userEvent.setup();
    renderRoute("/plan");
    expect(await screen.findByText("Verifier not available yet")).toBeInTheDocument();
    expect(screen.getByText(/The verifier is not available yet/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Generate plan" }));
    const dialog = screen.getByRole("dialog", { name: "Generate plan" });
    await user.click(within(dialog).getByRole("button", { name: "Generate" }));
    expect(await within(dialog).findByText(/Plan generation is not available yet/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Close" }));

    await user.click(screen.getByRole("button", { name: "AI advisor" }));
    const advisor = screen.getByRole("dialog", { name: "AI advisor" });
    expect(within(advisor).getByText("Generative AI")).toBeInTheDocument();
    await user.type(within(advisor).getByLabelText("Ask the advisor"), "Is TEST 20000 hard?");
    await user.click(within(advisor).getByRole("button", { name: "Send" }));
    expect(await within(advisor).findByText(/The advisor is not available yet/)).toBeInTheDocument();
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
    expect(within(dialog).getByText("In review")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Save programs" }));
    await user.click(screen.getByRole("button", { name: "Requirements" }));
    const node = await screen.findByRole("button", { name: /^Fake theory part/ });
    await waitFor(() => expect(node).toHaveTextContent("0 of 1 courses"));
    // Errors stay subtle: a small count on "Check plan", the list inside the panel.
    expect(await screen.findByRole("button", { name: "Check plan (1 error)" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Check plan (1 error)" }));
    expect(await screen.findByText("1 error")).toBeInTheDocument();
  });
});
