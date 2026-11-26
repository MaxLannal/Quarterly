import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { emptyPlan } from "@/features/planner/planModel";
import { loadPlans, newLocalId, upsertPlan, type LocalPlan } from "@/features/planner/localPlans";
import { renderRoute } from "@/test-utils";
import type { Proposal } from "./proposals";

const panel = () => screen.findByRole("heading", { name: "Ask Quarterly", level: 2 });
const proposal = (title: string) => screen.findByRole("article", { name: `Proposal: ${title}` });

async function generateWithInterest(user: ReturnType<typeof userEvent.setup>) {
  renderRoute("/plan");
  await user.click(await screen.findByRole("button", { name: "Generate plan" }));
  const question = await screen.findByTestId("planner-question");
  await user.type(within(question).getByLabelText("Your answer"), "software testing");
  await user.click(within(question).getByRole("button", { name: "Send" }));
  await proposal("Test introductory sequence");
}

function stored(extra: Partial<LocalPlan>): LocalPlan {
  const plan: LocalPlan = { localId: newLocalId(), name: "My Plan", isPrimary: true, state: emptyPlan("2099-00"), updatedDay: "2099-01-01", ...extra };
  upsertPlan(plan);
  return plan;
}

const pending = (over: Partial<Proposal> = {}): Proposal => ({
  id: "r:g1",
  changeSetId: null,
  groupId: "g1",
  title: "Stored proposal",
  kind: "major",
  ops: [{ op: "add", course: "TEST 10000", slot_ref: null, term: "2099-AU", status: "planned", grading: "letter", locked: false, units: null }],
  why: "Because you like testing.",
  citations: [],
  rules: [],
  status: "proposed",
  runId: "r",
  ...over,
});

describe("the planner panel", () => {
  it("panel is hidden until Generate plan", async () => {
    const user = userEvent.setup();
    renderRoute("/plan");
    const generate = await screen.findByRole("button", { name: "Generate plan" });
    expect(screen.queryByRole("heading", { name: "Ask Quarterly", level: 2 })).not.toBeInTheDocument();
    await user.click(generate);
    expect(await panel()).toBeInTheDocument();
    expect(screen.queryByText("Generative AI", { exact: true })).not.toBeInTheDocument(); // FEEDBACK 2026-11-16
    expect(screen.getByText(/Answers are written by an AI/)).toBeInTheDocument();
  });

  it("focus moves into the panel and Escape hides it", async () => {
    const user = userEvent.setup();
    renderRoute("/plan");
    const ask = await screen.findByRole("button", { name: "Ask Quarterly" });
    await user.click(ask);
    await panel();
    await waitFor(() => expect(screen.getByLabelText("Ask or tell the planner")).toHaveFocus());
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Ask Quarterly", level: 2 })).not.toBeInTheDocument());
  });

  it("question shows options and Other, and its answer leads to proposals", async () => {
    const user = userEvent.setup();
    await generateWithInterest(user);
    expect(screen.getByText("You answered: software testing")).toBeInTheDocument();
    expect(await proposal("Test methods")).toBeInTheDocument();
    expect(await proposal("Electives for testing")).toBeInTheDocument();
    const why = within(await proposal("Test introductory sequence")).getByText(/You said you are interested in software testing/);
    expect(why).toBeInTheDocument();
    expect(loadPlans().plans[0]?.profileAnswers).toEqual({ interests: ["software testing"] });
  });

  it("question survives reload", async () => {
    const user = userEvent.setup();
    const first = renderRoute("/plan");
    await user.click(await screen.findByRole("button", { name: "Generate plan" }));
    await screen.findByTestId("planner-question");
    first.unmount();
    renderRoute("/plan");
    await user.click(await screen.findByRole("button", { name: "Ask Quarterly" }));
    expect(await screen.findByTestId("planner-question")).toHaveTextContent("Which subjects or topics interest you most?");
  });

  it("new proposals are announced", async () => {
    const user = userEvent.setup();
    await generateWithInterest(user);
    await waitFor(() => expect(screen.getByTestId("planner-live")).toHaveTextContent(/New proposal: /));
  });

  it("accept applies the ops and locks the items", async () => {
    const user = userEvent.setup();
    await generateWithInterest(user);
    await user.click(within(await proposal("Test introductory sequence")).getByRole("button", { name: "Accept" }));
    const autumn = await screen.findByTestId("quarter-2099-AU");
    await waitFor(() => expect(within(autumn).getByRole("button", { name: "TEST 10000 is locked" })).toBeInTheDocument());
    expect(screen.queryByRole("article", { name: "Proposal: Test introductory sequence" })).not.toBeInTheDocument();
    expect(loadPlans().plans[0]?.history?.[0]?.label).toBe("Accepted: Test introductory sequence");
  });

  it("reject removes the blocks", async () => {
    const user = userEvent.setup();
    await generateWithInterest(user);
    expect(screen.getAllByRole("button", { name: /proposed in Test methods/ }).length).toBeGreaterThan(0);
    await user.click(within(await proposal("Test methods")).getByRole("button", { name: "Reject" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: /proposed in Test methods/ })).not.toBeInTheDocument());
  });

  it("accept all applies every group", async () => {
    const user = userEvent.setup();
    await generateWithInterest(user);
    await user.click(screen.getByRole("button", { name: "Accept all" }));
    await waitFor(() => expect(screen.queryAllByTestId("proposal-block")).toHaveLength(0));
    expect(within(screen.getByTestId("quarter-2101-AU")).getByText("TEST 25100")).toBeInTheDocument();
  });

  it("stale proposal shows ask again", async () => {
    const user = userEvent.setup();
    const items = [{ course: "TEST 10000", term: "2100-WI", status: "planned" as const, grading: "letter" as const, locked: false }];
    stored({ state: { ...emptyPlan("2099-00"), items }, proposals: [pending()], chat: [{ kind: "proposal", proposalId: "r:g1" }] });
    renderRoute("/plan");
    const card = await proposal("Stored proposal");
    await user.click(within(card).getByRole("button", { name: "Accept" }));
    expect(await within(card).findByText("This proposal no longer fits your plan.")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Ask again" })).toBeInTheDocument();
  });

  it("panel reopens after reload while proposals are pending", async () => {
    stored({ proposals: [pending()], chat: [{ kind: "proposal", proposalId: "r:g1" }] });
    renderRoute("/plan");
    expect(await panel()).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /^TEST 10000.*proposed in Stored proposal$/ })).toBeInTheDocument();
  });

  it("clear chat empties the thread after confirm", async () => {
    const user = userEvent.setup();
    await generateWithInterest(user);
    await user.click(screen.getByRole("button", { name: "Clear chat" }));
    const dialog = await screen.findByRole("dialog", { name: "Clear the chat?" });
    await user.click(within(dialog).getByRole("button", { name: "Clear chat" }));
    await waitFor(() => expect(screen.queryByTestId("planner-question")).not.toBeInTheDocument());
    expect(screen.getAllByTestId("proposal-block").length).toBeGreaterThan(0); // proposals stay on the plan
  });

  it("the chat records a preference for a plan in the browser", async () => {
    const user = userEvent.setup();
    renderRoute("/plan");
    await user.click(await screen.findByRole("button", { name: "Ask Quarterly" }));
    await user.type(await screen.findByLabelText("Ask or tell the planner"), "I hate TEST 20000{Enter}");
    expect(await screen.findByText("Noted: I will not propose TEST 20000 again.")).toBeInTheDocument();
    await waitFor(() => expect(loadPlans().plans[0]?.workingNotes).toContain("avoid · I hate TEST 20000 [TEST 20000]"));
  });
});
