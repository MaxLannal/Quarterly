import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderRoute } from "@/test-utils";
import type { FeedPage } from "./api";
import { arrange, noteIds, tickerCourses } from "./arrange";
import { wrap } from "./art/BookCover";
import { drawMotif, MOTIFS } from "./art/motifs";
import { palette } from "./art/palette";
import { hash, rng } from "./art/rng";

function course(id: string, category: string): FeedPage["items"][number] {
  return {
    kind: "course",
    id: `course:${id}`,
    code: id,
    title: `Title ${id}`,
    subject: id.split(" ")[0]!,
    category: { key: category, label: category, motif: "lattice" },
    units: 100,
    excerpt: "",
    core_tags: [],
    words: [],
    illustration: { seed: 1, motif: "lattice", palette: 0 },
    books: [],
    stats: null,
    reason: "r",
    commons_count: 0,
  };
}

const page = (items: FeedPage["items"]): FeedPage => ({
  tab: "for_you",
  items,
  next_cursor: null,
  categories_applied: [],
  headline: "h",
  personalized: false,
});

describe("arranging the loaded pages", () => {
  it("drops repeats and hidden items and moves less-wanted categories down", () => {
    const pages = [page([course("A 1", "math"), course("B 1", "arts"), course("C 1", "math")]), page([course("A 1", "math"), course("D 1", "life")])];
    expect(arrange(pages, new Set(), {}).map((i) => i.id)).toEqual(["course:A 1", "course:B 1", "course:C 1", "course:D 1"]);
    expect(arrange(pages, new Set(["course:B 1"]), { math: 1 }).map((i) => i.id)).toEqual(["course:A 1", "course:C 1", "course:D 1"]);
    expect(arrange([page([course("A 1", "math"), course("B 1", "arts")])], new Set(), { math: 1 }).map((i) => i.id)).toEqual(["course:B 1", "course:A 1"]);
    expect(arrange(pages, new Set(), { math: 3 }).map((i) => i.id)).toEqual(["course:B 1", "course:D 1"]);
  });

  it("asks the curator about at most twelve items and fills the ticker with courses", () => {
    const many = page(Array.from({ length: 15 }, (_, i) => course(`X ${i}`, "math")));
    expect(noteIds(many)).toHaveLength(12);
    expect(tickerCourses(many.items, 3).map((c) => c.code)).toEqual(["X 0", "X 1", "X 2"]);
  });
});

describe("generated art", () => {
  it("is deterministic and draws every motif", () => {
    expect(hash("CMSC 14100")).toBe(hash("CMSC 14100"));
    const a = rng(42);
    const b = rng(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
    for (const motif of Object.keys(MOTIFS)) expect(drawMotif(motif, rng(7), palette(3))).toBeTruthy();
    expect(Object.keys(MOTIFS)).toHaveLength(17);
  });

  it("wraps a cover title on whole words", () => {
    expect(wrap("The Structure of Scientific Revolutions", 13, 4)).toEqual(["The Structure", "of Scientific", "Revolutions"]);
    expect(wrap("A B C D E F G H", 1, 2)).toEqual(["A", "B…"]);
  });
});

describe("the feed page", () => {
  it("shows the hero, the focus chips, the tabs and course cards that link to their pages", async () => {
    renderRoute("/feed");
    expect(await screen.findByRole("heading", { level: 1, name: /A river of ideas/ })).toBeInTheDocument();
    const focus = await screen.findByRole("group", { name: "Your focus" });
    const chip = within(focus).getByRole("button", { name: "The Core" });
    expect(chip).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(chip);
    expect(chip).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("tab", { name: "For you" })).toHaveAttribute("aria-selected", "true");
    const link = await screen.findByRole("link", { name: "Fake Introduction I" });
    expect(link).toHaveAttribute("href", "/courses/TEST%2010000");
    expect(screen.getAllByText("From the Quarterly shelf").length).toBeGreaterThan(0);
  });

  it("explains the Following tab to a logged-out reader", async () => {
    renderRoute("/feed?tab=following");
    expect(await screen.findByRole("heading", { name: "Follow courses and routes to fill this tab" })).toBeInTheDocument();
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByRole("link", { name: "Log in" })).toHaveAttribute("href", expect.stringContaining("/login"));
  });
});
