import { DndContext } from "@dnd-kit/core";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import type { PlanState } from "@/api/types";
import type { ProposedBlock } from "@/features/planner-agent/proposals";
import { PlannerContext, type PlannerContextValue } from "./context";
import { emptyPlan } from "./planModel";
import { PlanGrid } from "./PlanGrid";

function setup(plan: PlanState, extra: Partial<PlannerContextValue> = {}) {
  const ctx: PlannerContextValue = {
    plan,
    courses: new Map(),
    programs: [],
    issues: [],
    highlight: { items: new Set(), terms: new Set() },
    tags: new Map(),
    edit: vi.fn(),
    applyOps: vi.fn(),
    openMoveTo: vi.fn(),
    openAddTo: vi.fn(),
    proposals: new Map(),
    proposalTitles: new Map(),
    glow: new Set(),
    selectProposal: vi.fn(),
    openDetails: vi.fn(),
    openSummers: new Set(),
    setSummerOpen: vi.fn(),
    ...extra,
  };
  const wrap = (node: ReactNode) => (
    <MemoryRouter>
      <PlannerContext.Provider value={ctx}>
        <DndContext>{node}</DndContext>
      </PlannerContext.Provider>
    </MemoryRouter>
  );
  render(wrap(<PlanGrid name="My Plan" onRename={vi.fn()} showSummer={false} onToggleSummer={vi.fn()} onGraduation={vi.fn()} onAddYear={vi.fn()} />));
  return ctx;
}

const base = (): PlanState => ({ ...emptyPlan("2099-00"), entry_term: "2099-AU", graduation_term: "2103-SP" });

describe("PlanGrid as four year-columns", () => {
  it("renders one column per year with four quarter slots", () => {
    setup(base());
    const years = screen.getAllByTestId(/^year-\d$/);
    expect(years).toHaveLength(4);
    const first = within(years[0]!);
    expect(first.getByRole("button", { name: "+ Summer 2099" })).toBeInTheDocument();
    for (const t of ["2099-AU", "2100-WI", "2100-SP"]) expect(first.getByTestId(`quarter-${t}`)).toBeInTheDocument();
    expect(first.queryByTestId("quarter-2099-SU")).not.toBeInTheDocument();
  });

  it("summer row is collapsed until it has a course", () => {
    setup({ ...base(), items: [{ course: "TEST 10000", term: "2100-SU", status: "planned", grading: "letter", locked: false }] });
    expect(screen.getByTestId("quarter-2100-SU")).toBeInTheDocument();
    expect(screen.queryByTestId("quarter-2101-SU")).not.toBeInTheDocument();
  });

  it("opens one year's summer from its row", async () => {
    const ctx = setup(base());
    await userEvent.click(screen.getByRole("button", { name: "+ Summer 2100" }));
    expect(ctx.setSummerOpen).toHaveBeenCalledWith(2, true);
  });
});

describe("proposal blocks", () => {
  const blocks = (b: Record<string, ProposedBlock[]>) => new Map(Object.entries(b));

  it("proposal blocks are dashed with a Proposed tag and the group title as accessible name", () => {
    setup(base(), {
      proposals: blocks({ "2099-AU": [{ proposalId: "p1", course: "TEST 10000", action: "add" }] }),
      proposalTitles: new Map([["p1", "Test introductory sequence"]]),
    });
    const block = screen.getByRole("button", { name: /^TEST 10000.*proposed in Test introductory sequence$/ });
    expect(block).toHaveAttribute("data-testid", "proposal-block");
    expect(block.className).toContain("border-dashed");
    expect(within(block).getByText("Proposed")).toBeInTheDocument();
  });

  it("remove proposals strike through the existing card", () => {
    setup(
      { ...base(), items: [{ id: "i1", course: "TEST 20000", term: "2099-AU", status: "planned", grading: "letter", locked: false }] },
      { proposals: blocks({ "2099-AU": [{ proposalId: "p2", course: "TEST 20000", action: "remove" }] }), proposalTitles: new Map([["p2", "Courses this plan replaces"]]) },
    );
    const card = screen.getByTestId("course-card");
    expect(card).toHaveAttribute("data-proposed-remove", "true");
    expect(within(card).getByText("Proposed: remove")).toBeInTheDocument();
  });

  it("clicking a proposal block selects its proposal", async () => {
    const ctx = setup(base(), {
      proposals: blocks({ "2099-AU": [{ proposalId: "p1", course: "TEST 10000", action: "add" }] }),
      proposalTitles: new Map([["p1", "Intro"]]),
    });
    await userEvent.click(screen.getByRole("button", { name: /TEST 10000.*proposed in Intro/ }));
    expect(ctx.selectProposal).toHaveBeenCalledWith("p1");
  });

  it("glow class only on blocks of the lit proposal", () => {
    setup(base(), {
      proposals: blocks({
        "2099-AU": [{ proposalId: "p1", course: "TEST 10000", action: "add" }],
        "2100-WI": [{ proposalId: "p2", course: "TEST 20000", action: "add" }],
      }),
      proposalTitles: new Map([["p1", "A"], ["p2", "B"]]),
      glow: new Set(["p1"]),
    });
    expect(screen.getByRole("button", { name: /TEST 10000/ }).className).toContain("glow-ring");
    expect(screen.getByRole("button", { name: /TEST 20000/ }).className).not.toContain("glow-ring");
  });
});
