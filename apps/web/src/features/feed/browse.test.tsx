import { act, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { resetSession, signedOut } from "@/features/auth/session";
import { renderRoute } from "@/test-utils";
import { drawMotif, MOTIFS } from "./art/motifs";
import { palette } from "./art/palette";
import { hash, rng } from "./art/rng";

describe("generated art", () => {
  it("is deterministic and draws every motif", () => {
    expect(hash("CMSC 14100")).toBe(hash("CMSC 14100"));
    const a = rng(42);
    const b = rng(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
    for (const motif of Object.keys(MOTIFS)) expect(drawMotif(motif, rng(7), palette(3))).toBeTruthy();
    expect(Object.keys(MOTIFS)).toHaveLength(17);
  });
});

describe("the Catalog's browse rows (issue #19)", () => {
  beforeEach(() => resetSession());
  afterEach(() => {
    window.sessionStorage.removeItem("quarterly.mock.session");
    resetSession();
  });

  it("shows new courses, spotlights and Commons quotes before a search, and no ratings logged out", async () => {
    renderRoute("/courses");
    expect(await screen.findByRole("heading", { level: 1, name: "Catalog" })).toBeInTheDocument();
    const fresh = await screen.findByRole("region", { name: "Newly released courses" });
    expect(within(fresh).getByRole("link", { name: /Fake Introduction II/ })).toHaveAttribute("href", "/courses/TEST%2010100");
    const spotlights = screen.getByRole("region", { name: "Course spotlights" });
    expect(within(spotlights).getByRole("link", { name: "Fake Introduction I" })).toHaveAttribute("href", "/courses/TEST%2010000");
    // Since issue #20, /forum lists reviews too: the "questions" link opens the discussions only.
    expect(within(spotlights).getByRole("link", { name: "1 question about it in the Forum" })).toHaveAttribute(
      "href",
      "/forum?course=TEST%2010000&type=discussion",
    );
    const quotes = screen.getByRole("region", { name: "What students say" });
    expect(within(quotes).getByText(/take the first course in Autumn/)).toBeInTheDocument();
    expect(within(quotes).queryByText(/hard but fair/)).toBeNull(); // forum posts need a login
    expect(screen.getByText(/to see student ratings/)).toBeInTheDocument();
    expect(screen.queryByText(/Student rating:/)).toBeNull();
  });

  it("shows forum quotes and the rating summary to a logged-in student", async () => {
    window.sessionStorage.setItem("quarterly.mock.session", "1");
    renderRoute("/courses");
    const spotlights = await screen.findByRole("region", { name: "Course spotlights" });
    expect(await within(spotlights).findByText(/4\.2 \/ 5/)).toBeInTheDocument();
    expect(within(spotlights).getAllByText("No reviews yet").length).toBeGreaterThan(0);
    const quotes = screen.getByRole("region", { name: "What students say" });
    expect(await within(quotes).findByText(/hard but fair/)).toBeInTheDocument();
    expect(screen.queryByText(/to see student ratings/)).toBeNull();
  });

  it("hides the ratings at once when the student logs out (no ratings from the cache)", async () => {
    window.sessionStorage.setItem("quarterly.mock.session", "1");
    renderRoute("/courses?q=Fake%20Introduction");
    const results = await screen.findByRole("region", { name: "Results" });
    expect(await within(results).findByText(/4\.2 \/ 5/)).toBeInTheDocument();
    window.sessionStorage.removeItem("quarterly.mock.session");
    act(() => signedOut());
    await waitFor(() => expect(screen.queryByText(/Student rating:/)).toBeNull());
    expect(screen.getByText(/to see student ratings/)).toBeInTheDocument();
  });

  it("lists results with their ratings after a search, and the rows go away", async () => {
    window.sessionStorage.setItem("quarterly.mock.session", "1");
    renderRoute("/courses?q=Fake%20Introduction");
    const results = await screen.findByRole("region", { name: "Results" });
    expect(await within(results).findByText(/4\.2 \/ 5/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Course spotlights" })).toBeNull();
  });

  it("sends the old Feed page to the Catalog", async () => {
    const { router } = renderRoute("/feed?tab=following");
    expect(await screen.findByRole("heading", { level: 1, name: "Catalog" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/courses");
  });
});
