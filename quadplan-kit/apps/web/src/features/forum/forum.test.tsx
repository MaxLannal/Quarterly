import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { resetSession } from "@/features/auth/session";
import { renderRoute } from "@/test-utils";
import type { Comment } from "./api";
import { buildTree } from "./CommentTree";
import { relativeDay } from "./format";

function logIn() {
  window.sessionStorage.setItem("quarterly.mock.session", "1");
}

beforeEach(() => {
  resetSession();
});

describe("relativeDay", () => {
  const today = new Date(2026, 10, 14);
  it.each([
    ["2026-11-14", "today"],
    ["2026-11-13", "yesterday"],
    ["2026-11-10", "4 days ago"],
    ["2026-11-07", "1 week ago"],
    ["2026-10-20", "3 weeks ago"],
    ["2026-08-01", "3 months ago"],
    ["2024-11-01", "2 years ago"],
  ])("%s is %s", (day, phrase) => {
    expect(relativeDay(day, today)).toBe(phrase);
  });
});

describe("buildTree", () => {
  it("nests a depth-first list and keeps sibling order", () => {
    const c = (id: number, parent: number | null, depth: number) =>
      ({ id, parent_id: parent, depth, post_id: 1, pseudonym: "x", body_md: "", body_html: "", score: 0, status: "visible", created_day: "2099-01-01" }) as Comment;
    const roots = buildTree([c(1, null, 0), c(3, 1, 1), c(2, 1, 1), c(4, null, 0)]);
    expect(roots.map((n) => n.comment.id)).toEqual([1, 4]);
    expect(roots[0]?.children.map((n) => n.comment.id)).toEqual([3, 2]);
  });
});

describe("forum pages", () => {
  it("asks for a login when logged out", async () => {
    renderRoute("/courses/TEST%2010000/i/fake-instructor-a");
    const notice = (await screen.findByText(/Reviews and discussion are for logged-in students/)).closest("div") as HTMLElement;
    expect(screen.getByRole("heading", { level: 1, name: "Course × instructor forum" })).toBeInTheDocument();
    // After logging in, the student comes back to this page (P08-10).
    const back = encodeURIComponent("/courses/TEST%2010000/i/fake-instructor-a");
    expect(within(notice).getByRole("link", { name: "Log in" })).toHaveAttribute("href", `/login?next=${back}`);
    expect(within(notice).getByRole("link", { name: "create an account" })).toHaveAttribute("href", `/signup?next=${back}`);
  });

  it("shows the header, ratings, summary slot, tabs and posts", async () => {
    logIn();
    renderRoute("/courses/TEST%2010000/i/fake-instructor-a");
    expect(await screen.findByRole("heading", { level: 1, name: /Fake Introduction I with Fake Instructor A/ })).toBeInTheDocument();
    expect(screen.getByText("No summary yet")).toBeInTheDocument();
    expect(screen.getByText("Overall 5: 1 rating")).toBeInTheDocument();
    expect(await screen.findByText("Fake Heron")).toBeInTheDocument();
    expect(screen.getAllByText("Took it in Autumn 2099").length).toBeGreaterThan(0);
    const tabs = screen.getByRole("tablist", { name: "Reviews and discussion" });
    await userEvent.click(within(tabs).getByRole("tab", { name: "Discussion" }));
    expect(await screen.findByRole("link", { name: "Fake question: is the midterm curved?" })).toBeInTheDocument();
  });

  it("requires every rating before a review is posted, then posts it", async () => {
    logIn();
    renderRoute("/courses/TEST%2010000/i/fake-instructor-a");
    await userEvent.click(await screen.findByRole("button", { name: "Write a review" }));
    const form = screen.getByRole("form", { name: "Write a review" });
    expect(screen.getByRole("complementary", { name: "Community rules" })).toHaveTextContent("No names of other students.");
    await userEvent.click(within(form).getByRole("button", { name: "Post review" }));
    expect(within(form).getByText("Give all three ratings.")).toBeInTheDocument();
    expect(within(form).getByText("Pick the term you took it.")).toBeInTheDocument();

    for (const name of ["Overall 4 of 5", "Difficulty 3 of 5", "Intellectual intensity 4 of 5"]) {
      await userEvent.click(within(form).getByRole("radio", { name }));
    }
    await userEvent.type(within(form).getByLabelText("Workload: hours per week outside class"), "9");
    await userEvent.click(within(form).getByRole("radio", { name: "Yes" }));
    await userEvent.selectOptions(within(form).getByLabelText("Term you took it"), "2099-AU");
    await userEvent.type(within(form).getByLabelText("Your review"), "Fake: good course.");
    await userEvent.click(within(form).getByRole("button", { name: "Post review" }));
    expect(await screen.findByText("Fake Wren")).toBeInTheDocument();
  });

  it("folds replies below depth 6 in the thread view", async () => {
    logIn();
    renderRoute("/courses/TEST%2010000/i/fake-instructor-a/t/3");
    expect(await screen.findByRole("heading", { level: 1, name: "Fake question: is the midterm curved?" })).toBeInTheDocument();
    expect(screen.getByText("Fake reply at depth 5.")).toBeInTheDocument();
    expect(screen.queryByText("Fake reply at depth 6.")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continue this thread (3 more replies)" }));
    expect(screen.getByText("Fake reply at depth 8.")).toBeInTheDocument();
  });

  it("reports a post through the dialog", async () => {
    logIn();
    renderRoute("/courses/TEST%2010000/i/fake-instructor-a/t/3");
    await userEvent.click(await screen.findByRole("button", { name: "Report discussion by Fake Lark" }));
    const dialog = screen.getByRole("dialog", { name: "Report this post" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Send report" }));
    expect(within(dialog).getByText("Choose a reason.")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("radio", { name: "Spam or off topic" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Send report" }));
    await waitFor(() => expect(within(dialog).getByText("Thanks. A moderator will look at it.")).toBeInTheDocument());
  });

  it("lists instructors publicly and hides ratings until login", async () => {
    renderRoute("/instructors/fake-instructor-a");
    expect(await screen.findByRole("heading", { level: 1, name: "Fake Instructor A" })).toBeInTheDocument();
    expect(screen.getByText(/to see ratings and read reviews/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Reviews and discussion" })).not.toBeInTheDocument();
  });
});
