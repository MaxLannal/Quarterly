import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { newQueryClient } from "@/test-utils";
import type { ChangeOp, Citation } from "@/api/types";
import { resetSession } from "@/features/auth/session";
import { sse } from "@/mocks/agents";
import { server } from "@/mocks/node";
import { emptyPlan } from "@/features/planner/planModel";
import { AdvisorPanel, CitationChip, confirmationPhrase } from "./AdvisorPanel";

const plan = emptyPlan("2099-00");

function renderPanel(onApply: (ops: ChangeOp[]) => boolean, planId: string | null = null) {
  return render(
    <QueryClientProvider client={newQueryClient()}>
      <MemoryRouter>
        <AdvisorPanel plan={plan} planId={planId} onApply={onApply} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function ask(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Ask the advisor"), text);
  await user.click(screen.getByRole("button", { name: "Send" }));
}

describe("AdvisorPanel", () => {
  it("shows the typed confirmation for a proposal and applies it when typed", async () => {
    const onApply = vi.fn(() => true);
    let sent: Record<string, unknown> | null = null;
    renderPanel(onApply);
    await ask("Please add a lighter elective");
    const card = await screen.findByRole("article", { name: "Proposed change" });
    expect(within(card).getByText(/I agree to add TEST 25200 to Autumn 2099/)).toBeInTheDocument();

    server.use(
      http.post("*/api/agents/chat", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        const latest = sent.latest_proposal as never;
        return sse([{ type: "confirm", change_set: latest, confirmation_text: "apply it" }, { type: "done", run_id: "r" }]);
      }),
    );
    await ask("apply it");
    expect(await within(card).findByText("Applied.")).toBeInTheDocument();
    expect(onApply).toHaveBeenCalledWith([expect.objectContaining({ op: "add", course: "TEST 25200" })]);
    // A plan in the browser sends its own history and latest card.
    expect(sent).not.toBeNull();
    const body = sent as unknown as { history: { role: string }[]; latest_proposal: { ops: unknown[] } };
    expect(body.history.map((t) => t.role)).toEqual(["user", "assistant"]);
    expect(body.latest_proposal.ops).toHaveLength(1);
  });

  it("applies a saved plan's confirmation through the change-set endpoint", async () => {
    const onApply = vi.fn(() => true);
    let applied: Record<string, unknown> | null = null;
    const cs = {
      id: "cs-1",
      plan_id: "p1",
      origin: "chat" as const,
      ops: [{ op: "add" as const, course: "TEST 25200", slot_ref: null, term: "2099-AU", status: "planned" as const, grading: "letter" as const, locked: false, units: null }],
      base_plan_hash: "h",
      status: "proposed" as const,
      preview_report: null,
    };
    server.use(
      http.get("*/api/agents/chat/history", () =>
        HttpResponse.json({ run_id: "r1", entries: [{ role: "user", text: "Add it", citations: [], change_set: null }, { role: "proposal", text: "", citations: [], change_set: cs }] }),
      ),
      http.post("*/api/agents/chat", () => sse([{ type: "confirm", change_set: cs, confirmation_text: "I agree to add TEST 25200 to Autumn 2099" }, { type: "done", run_id: "r1" }])),
      http.post("*/api/plans/:pid/changesets/:cs/apply", async ({ request }) => {
        applied = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({});
      }),
    );
    renderPanel(onApply, "p1");
    expect(await screen.findByText("Add it")).toBeInTheDocument();
    await ask("I agree to add TEST 25200 to Autumn 2099");
    expect(await screen.findByText("Applied.")).toBeInTheDocument();
    expect(applied).toEqual({ base_plan_hash: "h", terms: null, confirmation_text: "I agree to add TEST 25200 to Autumn 2099" });
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("shows a refusal and server errors", async () => {
    renderPanel(() => true);
    await ask("Tell me a joke");
    expect(await screen.findByText("I can only help with planning your courses.")).toBeInTheDocument();
    server.use(http.post("*/api/agents/chat", () => sse([{ type: "error", message: "The advisor can't answer right now." }, { type: "done", run_id: "r" }])));
    await ask("Which elective is lighter?");
    expect(await screen.findByRole("alert")).toHaveTextContent("The advisor can't answer right now.");
  });
});

describe("CitationChip", () => {
  const cites: Citation[] = [
    { kind: "course", id: "TEST 25200", label: "TEST 25200" },
    { kind: "attribute", id: "TEST 25200:workload_hours", label: "TEST 25200: workload hours" },
    { kind: "post", id: "3", label: "Student post #3" },
    { kind: "summary", id: "1", label: "What students say" },
  ];
  function renderChips() {
    return render(
      <QueryClientProvider client={newQueryClient()}>
        <MemoryRouter>
          {cites.map((c) => (
            <CitationChip key={c.kind} c={c} />
          ))}
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }
  beforeEach(() => resetSession());

  it("links forum sources to their thread and page once logged in", async () => {
    window.sessionStorage.setItem("quarterly.mock.session", "1");
    renderChips();
    expect(screen.getByRole("link", { name: "TEST 25200: workload hours" })).toHaveAttribute("href", "/courses/TEST%2025200");
    expect(await screen.findByRole("link", { name: "Student post #3" })).toHaveAttribute("href", "/courses/TEST%2010000/i/fake-instructor-a/t/3");
    expect(await screen.findByRole("link", { name: "What students say" })).toHaveAttribute("href", "/courses/TEST%2010000/i/fake-instructor-a");
  });

  it("keeps forum sources as plain chips when logged out", async () => {
    window.sessionStorage.removeItem("quarterly.mock.session");
    renderChips();
    await waitFor(() => expect(screen.getAllByRole("link")).toHaveLength(2));
    expect(screen.getByText("Student post #3").tagName).toBe("SPAN");
    expect(screen.getByText("What students say").tagName).toBe("SPAN");
  });
});

describe("confirmationPhrase", () => {
  it("writes the sentence the server's parser reads, or nothing", () => {
    expect(
      confirmationPhrase([
        { op: "add", course: "MATH 20700", slot_ref: null, term: "2027-AU", status: "planned", grading: "letter", locked: false, units: null },
        { op: "move", course: "CMSC 14100", item_id: null, slot_ref: null, from_term: "2026-AU", to_term: "2027-WI" },
        { op: "remove", course: "PHIL 25000", item_id: null, slot_ref: null, term: null },
      ]),
    ).toBe("I agree to add MATH 20700 to Autumn 2027 and move CMSC 14100 from Autumn 2026 to Winter 2027 and remove PHIL 25000");
    expect(confirmationPhrase([{ op: "lock", course: "MATH 20700", item_id: null, slot_ref: null, term: null }])).toBeNull();
  });
});
