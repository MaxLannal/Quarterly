import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { emptyPlan } from "@/features/planner/planModel";
import { newLocalId, upsertPlan } from "@/features/planner/localPlans";
import { renderRoute } from "@/test-utils";
import type { Proposal } from "./proposals";
import { walkOrder } from "./useWalkthrough";

const lit = () => screen.queryAllByTestId("proposal-block").filter((b) => b.getAttribute("data-glow") === "true");
const litTitles = () => [...new Set(lit().map((b) => b.getAttribute("aria-label")?.split(", proposed in ")[1]))];

async function generated(user: ReturnType<typeof userEvent.setup>) {
  renderRoute("/plan");
  await user.click(await screen.findByRole("button", { name: "Generate plan" }));
  const question = await screen.findByTestId("planner-question");
  await user.type(within(question).getByLabelText("Your answer"), "machine learning");
  await user.click(within(question).getByRole("button", { name: "Send" }));
  return screen.findByTestId("walkthrough");
}

function proposal(id: string, kind: Proposal["kind"], course: string, term: string): Proposal {
  return {
    id, changeSetId: null, groupId: id, title: `Group ${id}`, kind, why: "x", citations: [], rules: [], status: "proposed", runId: "r",
    ops: [{ op: "add", course, slot_ref: null, term, status: "planned", grading: "letter", locked: false, units: null }],
  };  // fmt: skip
}

describe("the walkthrough", () => {
  it("orders majors first, then the Core, then electives, earliest quarter first", () => {
    const order = walkOrder([proposal("e", "elective", "TEST 25000", "2099-AU"), proposal("c", "core", "TEST 20000", "2100-WI"), proposal("m2", "major", "TEST 10100", "2100-WI"), proposal("m1", "major", "TEST 10000", "2099-AU")]);
    expect(order.map((p) => p.id)).toEqual(["m1", "m2", "c", "e"]);
  });

  it("starts after a generation and lights the first major group", async () => {
    const user = userEvent.setup();
    const card = await generated(user);
    expect(within(card).getByText("Step 1 of 3")).toBeInTheDocument();
    expect(within(card).getByRole("article", { name: "Walkthrough: Test introductory sequence" })).toHaveTextContent(/interested in machine learning/);
    await waitFor(() => expect(litTitles()).toEqual(["Test introductory sequence"]));
    expect(lit()).toHaveLength(3);
  });

  it("next and back move the glow", async () => {
    const user = userEvent.setup();
    const card = await generated(user);
    await user.click(within(card).getByRole("button", { name: "Next" }));
    expect(within(card).getByText("Step 2 of 3")).toBeInTheDocument();
    await waitFor(() => expect(litTitles()).toEqual(["Test methods"]));
    await user.click(within(card).getByRole("button", { name: "Back" }));
    await waitFor(() => expect(litTitles()).toEqual(["Test introductory sequence"]));
  });

  it("accept advances to the next group", async () => {
    const user = userEvent.setup();
    const card = await generated(user);
    await user.click(within(within(card).getByRole("article")).getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(within(card).getByText("Step 1 of 2")).toBeInTheDocument());
    expect(within(card).getByRole("article", { name: "Walkthrough: Test methods" })).toBeInTheDocument();
  });

  it("skip clears the glow", async () => {
    const user = userEvent.setup();
    const card = await generated(user);
    await user.click(within(card).getByRole("button", { name: "Skip tour" }));
    await waitFor(() => expect(screen.queryByTestId("walkthrough")).not.toBeInTheDocument());
    expect(lit()).toHaveLength(0);
    // "Walk me through it" on the plan card starts it again.
    await user.click(screen.getByRole("button", { name: "Walk me through it" }));
    expect(await screen.findByText("Step 1 of 3")).toBeInTheDocument();
  });

  it("opens a collapsed summer for its step", async () => {
    const user = userEvent.setup();
    const summer = proposal("s", "major", "TEST 10200", "2100-SU");
    const plan = { localId: newLocalId(), name: "My Plan", isPrimary: true, state: emptyPlan("2099-00"), updatedDay: "2099-01-01" };
    upsertPlan({
      ...plan,
      proposals: [summer, proposal("e", "elective", "TEST 25000", "2100-WI")],
      chat: [{ kind: "plan", event: { type: "plan", run_id: "r", verdict: "valid", issues: [], compromises: [], summary: "" } }],
    });
    renderRoute("/plan");
    expect(screen.queryByTestId("quarter-2100-SU")).toBeInTheDocument(); // it holds a proposal
    await user.click(await screen.findByRole("button", { name: "Walk me through it" }));
    expect(await screen.findByText("Step 1 of 2")).toBeInTheDocument();
    await waitFor(() => expect(within(screen.getByTestId("quarter-2100-SU")).getByRole("button", { name: /TEST 10200/ })).toHaveAttribute("data-glow", "true"));
  });
});
