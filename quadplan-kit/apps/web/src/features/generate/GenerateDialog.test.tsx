import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { MemoryRouter } from "react-router-dom";
import { sse } from "@/mocks/agents";
import { server } from "@/mocks/node";
import { emptyPlan } from "@/features/planner/planModel";
import { buildGenerateRequest, GenerateDialog } from "./GenerateDialog";
import { GENERATOR_MODE } from "./deterministic";

const plan = emptyPlan("2099-00");
const form = { scope: "remaining" as const, selectedTerms: [], load: 0, perTermLoad: {}, maxCourses: null, allowOverload: false, goals: [], interests: ["ML"], variants: 2 };

function renderDialog(planId: string | null = null) {
  return render(
    <MemoryRouter>
      <GenerateDialog open onClose={() => undefined} plan={plan} onApply={() => true} planId={planId} />
    </MemoryRouter>,
  );
}

describe("GenerateDialog (agent mode)", () => {
  it("uses the agent generator by default", () => {
    expect(GENERATOR_MODE).toBe("agent");
  });

  it("sends the saved plan id and today's quarter for 'remaining quarters'", () => {
    const body = buildGenerateRequest(plan, form, "p1", "2099-WI");
    expect(body.plan_id).toBe("p1");
    expect(body.today_term).toBe("2099-WI");
    expect(buildGenerateRequest(plan, { ...form, scope: "whole" }).today_term).toBeNull();
  });

  it("streams steps and variants with their rationale and sources", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole("button", { name: "Generate" }));
    const variant = await screen.findByRole("article", { name: "Variant Fake balanced" });
    expect(within(variant).getAllByText(/Fake rationale/).length).toBeGreaterThan(0);
    expect(within(variant).getByRole("list", { name: "Sources for Fake balanced" })).toBeInTheDocument();
  });

  it("explains an impossible request", async () => {
    server.use(
      http.post("*/api/agents/generate", () =>
        sse([
          { type: "step", name: "Solving", status: "done" },
          { type: "infeasible", message: "Graduating by Spring 2101 needs 5 more courses than your remaining quarters allow.", conflicts: [] },
          { type: "done", run_id: "r" },
        ]),
      ),
    );
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole("button", { name: "Generate" }));
    expect(await screen.findByText(/needs 5 more courses/)).toBeInTheDocument();
    expect(screen.getByText("No plan fits all of these settings.")).toBeInTheDocument();
  });
});
