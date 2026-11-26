import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { newQueryClient } from "@/test-utils";
import { AnswerControl } from "./AnswerControls";
import { TEST_QUESTIONS, testQuestion } from "./fixtures";

// Blocker 2 (review of PR #21): the taken-courses table sends the whole list on every change.
// It used to rebuild each row from the four columns it shows, so removing one course turned
// every other Pass/Fail course into a letter-graded one and dropped its units and lock.
describe("the taken-courses table on the dashboard", () => {
  const rows = [
    { course: "PHYS 13100", title: "Mechanics", term: "2025-AU", status: "completed" as const, grade: null, grading: "pass_fail" as const, units: 50, locked: true },
    { course: "PHYS 13200", title: "Electricity", term: "2026-WI", status: "completed" as const, grade: "B", grading: "letter" as const, units: null, locked: false },
  ];

  it("keeps the other courses' grading, units and lock when one is removed", async () => {
    const onChange = vi.fn();
    render(
      <QueryClientProvider client={newQueryClient()}>
        <AnswerControl question={testQuestion("taken_courses")} set={TEST_QUESTIONS} value={rows} onChange={onChange} classYear={2028} catalogYear="2026-27" layout="panel" />
      </QueryClientProvider>,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: /^Remove PHYS 13200/ }));
    expect(onChange).toHaveBeenCalledWith([{ course: "PHYS 13100", term: "2025-AU", status: "completed", grade: null, grading: "pass_fail", units: 50, locked: true }]);
  });
});

// Richard (2026-11-25): a student who is taking a course has no grade for it yet.
describe("a taken course in progress", () => {
  it("has its grade field disabled and emptied", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={newQueryClient()}>
        <AnswerControl question={testQuestion("taken_courses")} set={TEST_QUESTIONS} value={[]} onChange={vi.fn()} classYear={2028} catalogYear="2026-27" />
      </QueryClientProvider>,
    );
    const grade = screen.getByLabelText("Grade (optional)");
    await user.type(grade, "A-");
    await user.selectOptions(screen.getByLabelText("Status"), "in_progress");
    expect(grade).toBeDisabled();
    expect(grade).toHaveValue("");
    await user.selectOptions(screen.getByLabelText("Status"), "completed");
    expect(grade).toBeEnabled();
  });
});
