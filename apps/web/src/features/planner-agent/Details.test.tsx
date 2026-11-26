import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { emptyPlan } from "@/features/planner/planModel";
import { loadPlans, newLocalId, upsertPlan } from "@/features/planner/localPlans";
import { renderRoute } from "@/test-utils";

function withCourse() {
  upsertPlan({
    localId: newLocalId(),
    name: "My Plan",
    isPrimary: true,
    updatedDay: "2099-01-01",
    state: { ...emptyPlan("2099-00"), items: [{ id: "i1", course: "TEST 10000", term: "2099-AU", status: "planned", grading: "letter", locked: false }] },
  });
}

describe("course details and history", () => {
  it("clicking a course card opens its details", async () => {
    const user = userEvent.setup();
    withCourse();
    renderRoute("/plan");
    const card = await screen.findByTestId("course-card");
    await user.click(within(card).getByRole("button", { name: /details/ }));
    const details = await screen.findByRole("region", { name: "Course details" });
    expect(await within(details).findByRole("heading", { name: /TEST 10000/ })).toBeInTheDocument();
    await user.click(within(details).getByRole("button", { name: "Back to the chat" }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Course details" })).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Planner", level: 2 })).toBeInTheDocument();
  });

  it("history lists edits newest first and revert applies the inverse", async () => {
    const user = userEvent.setup();
    withCourse();
    renderRoute("/plan");
    const card = await screen.findByTestId("course-card");
    await user.click(within(card).getByRole("button", { name: "Actions for TEST 10000" }));
    await user.click(await screen.findByRole("menuitem", { name: "Remove" }));
    await waitFor(() => expect(screen.queryByTestId("course-card")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "History" }));
    const history = await screen.findByRole("region", { name: "Edit history" });
    const rows = within(history).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent(/Remove TEST 10000/);
    await user.click(within(rows[0]!).getByRole("button", { name: "Revert" }));
    expect(await screen.findByTestId("course-card")).toHaveAttribute("data-course", "TEST 10000");
    expect(within(history).getAllByRole("listitem")[0]).toHaveTextContent(/Reverted: Remove TEST 10000/);
    expect(loadPlans().plans[0]?.history).toHaveLength(2);
  });
});
