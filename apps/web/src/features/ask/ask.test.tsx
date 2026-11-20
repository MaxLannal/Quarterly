import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { contextOf, suggestionsFor } from "@/features/companion/suggestions";
import { renderRoute } from "@/test-utils";
import { ASK_KEY, historyOf, loadConversations, mergeStep, saveConversations, titleFrom } from "./conversations";
import { blocksOf, isInternalPath, isTrustedExternal, Markdown } from "./markdown";
import type { Conversation } from "./types";

function md(text: string, courses: string[] = []) {
  return render(
    <MemoryRouter>
      <Markdown text={text} courses={courses} />
    </MemoryRouter>,
  );
}

describe("the answer's markdown", () => {
  it("splits paragraphs and lists; a heading reads as a bold line", () => {
    expect(blocksOf("One\ntwo\n\n- a\n- b\n\n1. x\n2. y\n### Head")).toEqual([
      { kind: "p", text: "One\ntwo" },
      { kind: "ul", items: ["a", "b"] },
      { kind: "ol", items: ["x", "y"] },
      { kind: "p", text: "**Head**" },
    ]);
  });

  it("renders bold, italic, code and links as elements, never as HTML", () => {
    const { container } = md("**Bold** and *it* and `code` <img src=x onerror=alert(1)> [here](/courses/MATH%2015100)");
    expect(container.querySelector("strong")?.textContent).toBe("Bold");
    expect(container.querySelector("em")?.textContent).toBe("it");
    expect(container.querySelector("code")?.textContent).toBe("code");
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
    expect(screen.getByRole("link", { name: "here" })).toHaveAttribute("href", "/courses/MATH%2015100");
  });

  it("links only paths on this site and https pages on uchicago.edu", () => {
    md("[a](https://college.uchicago.edu/) [b](https://evil.example/) [c](javascript:alert(1)) [d](//evil.example)");
    const official = screen.getByRole("link", { name: /^a/ });
    expect(official).toHaveAttribute("target", "_blank");
    expect(official).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByRole("link", { name: "b" })).toBeNull();
    expect(screen.queryByRole("link", { name: "c" })).toBeNull();
    expect(screen.queryByRole("link", { name: "d" })).toBeNull();
    expect(isInternalPath("/x")).toBe(true);
    expect(isInternalPath("//x")).toBe(false);
    expect(isInternalPath("/\\x")).toBe(false);
    expect(isTrustedExternal("http://college.uchicago.edu/")).toBe(false);
    expect(isTrustedExternal("https://uchicago.edu.evil.example/")).toBe(false);
  });

  it("links the course codes the API confirmed, and only those", () => {
    md("Take MATH 15100 before MATH15200, not FAKE 99999.", ["MATH 15100", "MATH 15200"]);
    expect(screen.getByRole("link", { name: "MATH 15100" })).toHaveAttribute("href", "/courses/MATH%2015100");
    expect(screen.getByRole("link", { name: "MATH15200" })).toHaveAttribute("href", "/courses/MATH%2015200");
    expect(screen.queryByRole("link", { name: "FAKE 99999" })).toBeNull();
  });
});

describe("conversations in the browser", () => {
  beforeEach(() => localStorage.clear());

  it("titles a conversation by its first question", () => {
    expect(titleFrom("  What   is the Core? ")).toBe("What is the Core?");
    const long = titleFrom("How do I get into quantum computing research as a first-year student at UChicago?");
    expect(long.endsWith("…")).toBe(true);
    expect(long.length).toBeLessThanOrEqual(61);
  });

  it("closes a started step and keeps unrelated ones", () => {
    const started = { tool: "get_course", label: "Reading X", status: "started" as const };
    const steps = mergeStep(mergeStep([], started), { ...started, status: "done" });
    expect(steps).toEqual([{ ...started, status: "done" }]);
    expect(mergeStep(steps, { tool: "search_courses", label: "S", status: "started" })).toHaveLength(2);
  });

  it("sends only answered turns as history, and a reload stops a half-streamed answer", () => {
    const conv: Conversation = {
      id: "c1",
      title: "t",
      updatedAt: 1,
      turns: [
        { id: "u1", role: "user", text: "Hi" },
        { id: "a1", role: "assistant", status: "done", text: "Hello", citations: [], courses: [], followups: [], ai: true, steps: [] },
        { id: "u2", role: "user", text: "And?" },
        { id: "a2", role: "assistant", status: "streaming", text: "", citations: [], courses: [], followups: [], ai: true, steps: [] },
      ],
    };
    expect(historyOf(conv.turns)).toEqual([
      { role: "user", text: "Hi" },
      { role: "assistant", text: "Hello" },
      { role: "user", text: "And?" },
    ]);
    saveConversations(ASK_KEY, [conv]);
    const [loaded] = loadConversations(ASK_KEY);
    expect(loaded?.turns[3]).toMatchObject({ status: "stopped" });
    localStorage.setItem(ASK_KEY, "{not json");
    expect(loadConversations(ASK_KEY)).toEqual([]);
  });
});

describe("the companion's page context", () => {
  it("reads the course and the thread from the path", () => {
    expect(contextOf("/courses/MATH%2015100/i/someone")).toEqual({ page: "/courses/MATH%2015100/i/someone", course_code: "MATH 15100" });
    expect(contextOf("/forum/t/42")).toEqual({ page: "/forum/t/42", thread_id: 42 });
    expect(contextOf("/courses/not-a-code")).toEqual({ page: "/courses/not-a-code" });
    expect(suggestionsFor(contextOf("/courses/CMSC%2014100")).chips[0]).toBe("Is CMSC 14100 a good fit for me?");
    expect(suggestionsFor(contextOf("/feed")).chips).toHaveLength(3);
  });
});

/** The mock answer's first paragraph (its text is split by the course links inside it). */
const answerLine = (_: string, el: Element | null) => el?.tagName === "P" && /then TEST 10100 in Winter/.test(el.textContent ?? "");

describe("the Ask page", () => {
  beforeEach(() => localStorage.clear());

  it("asks the question from ?q=, streams the answer with its trace, and keeps the conversation", async () => {
    const { router } = renderRoute("/ask?q=What%20should%20I%20take%20first%3F");
    const answer = await screen.findByText(answerLine, {}, { timeout: 4000 });
    expect(router.state.location.search).toBe("");
    const article = answer.closest("article") as HTMLElement;
    expect(within(article).getByRole("link", { name: "TEST 10100" })).toHaveAttribute("href", "/courses/TEST%2010100");
    expect(within(article).getByText("Written by an AI and can be wrong.")).toBeInTheDocument();
    expect(within(article).getByRole("button", { name: /Looked at 2 sources/ })).toBeInTheDocument();
    const guide = within(article).getByRole("link", { name: /The Core curriculum/ });
    expect(guide).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("heading", { level: 1, name: "What should I take first?" })).toBeInTheDocument();
    expect(loadConversations(ASK_KEY)[0]?.turns).toHaveLength(2);

    await userEvent.click(within(article).getByRole("button", { name: /What comes after TEST 10100/ }));
    expect(await screen.findAllByText(answerLine)).toHaveLength(2);
  });

  it("shows the hero with example questions on a first visit, and no companion orb", () => {
    renderRoute("/ask");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Ask anything about UChicago.");
    expect(screen.getByRole("button", { name: /Which Core humanities sequence/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Open Quarterly companion/ })).toBeNull();
  });
});
