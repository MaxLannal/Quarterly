import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderRoute } from "@/test-utils";

function logIn(admin: boolean) {
  window.sessionStorage.setItem("quarterly.mock.session", "1");
  if (admin) window.sessionStorage.setItem("quarterly.mock.admin", "1");
}

afterEach(() => {
  window.sessionStorage.removeItem("quarterly.mock.session");
  window.sessionStorage.removeItem("quarterly.mock.admin");
});

describe("curator console", () => {
  it("is for admins only", async () => {
    logIn(false);
    renderRoute("/admin/review");
    expect(await screen.findByText("Only admins can review catalog changes.")).toBeInTheDocument();
  });

  it("shows each rule beside its source quote, with flags and checks", async () => {
    logIn(true);
    renderRoute("/admin/review");
    const card = await screen.findByRole("article", { name: "fake-science-bs 2099-00" });
    const tree = within(card).getByRole("region", { name: "Rule tree with source quotes" });
    expect(within(tree).getByText("“FAKE: the BS also requires TEST 20000.”")).toBeInTheDocument();
    expect(within(tree).getByText("The second run disagrees here (different).")).toBeInTheDocument();
    expect(within(card).getByText("(d) Two runs agree: look")).toBeInTheDocument();
    expect(within(card).getByText("(f) Golden plans: not run")).toBeInTheDocument();
    // Course batches can be accepted or rejected, not edited.
    const batch = screen.getByRole("article", { name: "TEST courses 2099-00" });
    expect(within(batch).queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(within(batch).getByText(/1 new course, 0 changed courses, 0 removed courses/)).toBeInTheDocument();
  });

  it("accepts a program version, then publishes it from the accepted list", async () => {
    const user = userEvent.setup();
    logIn(true);
    renderRoute("/admin/review");
    const card = await screen.findByRole("article", { name: "fake-science-bs 2099-00" });
    expect(within(card).queryByRole("button", { name: "Publish this version" })).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Accept" }));
    expect(await screen.findByText(/Accepted: fake-science-bs 2099-00\./)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Show"), "accepted");
    const accepted = await screen.findByRole("article", { name: "fake-science-bs 2099-00" });
    await user.click(within(accepted).getByRole("button", { name: "Publish this version" }));
    expect(await screen.findByText("Published fake-science-bs 2099-00. Students now see these rules.")).toBeInTheDocument();
  });

  it("edits a prerequisite as JSON and refuses text that is not JSON", async () => {
    const user = userEvent.setup();
    logIn(true);
    renderRoute("/admin/review");
    const card = await screen.findByRole("article", { name: "Prerequisite of TEST 20000 2099-00" });
    expect(within(card).getByText("“FAKE: TEST 10000 or TEST 99999.”")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Edit" }));
    const box = within(card).getByLabelText("Prerequisite (JSON)");
    await user.clear(box);
    await user.type(box, "not json");
    await user.click(within(card).getByRole("button", { name: "Save edit" }));
    expect(within(card).getByText("This is not valid JSON.")).toBeInTheDocument();
    await user.clear(box);
    await user.type(box, '"TEST 10000"');
    await user.click(within(card).getByRole("button", { name: "Save edit" }));
    expect(await screen.findByText("Saved your edit: Prerequisite of TEST 20000 2099-00.")).toBeInTheDocument();
  });
});
