import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { resetCommonsMock } from "@/mocks/commons";
import { renderRoute } from "@/test-utils";
import { MarkdownPreview, parseBlocks, parseInline, safeHref } from "./markdown";
import { applyFormat, applyMention, dayWords, findMention, searchTerms, summonsBot, toTag } from "./text";

describe("markdown preview", () => {
  it("parses the inline subset", () => {
    expect(parseInline("**bold** and _em_ and `x*y` and ~~old~~")).toEqual([
      { t: "strong", c: [{ t: "text", v: "bold" }] },
      { t: "text", v: " and " },
      { t: "em", c: [{ t: "text", v: "em" }] },
      { t: "text", v: " and " },
      { t: "code", v: "x*y" },
      { t: "text", v: " and " },
      { t: "del", c: [{ t: "text", v: "old" }] },
    ]);
    // snake_case words and lone stars stay text.
    expect(parseInline("my_var_name * 2")).toEqual([{ t: "text", v: "my_var_name * 2" }]);
    expect(parseInline("\\*not em\\*")).toEqual([{ t: "text", v: "*not em*" }]);
    expect(parseInline("line\nbreak")).toEqual([{ t: "text", v: "line" }, { t: "br" }, { t: "text", v: "break" }]);
  });

  it("links only to https", () => {
    expect(parseInline("[site](https://college.uchicago.edu/x)")).toEqual([
      { t: "a", href: "https://college.uchicago.edu/x", c: [{ t: "text", v: "site" }] },
    ]);
    expect(parseInline("[bad](javascript:alert(1))")).toEqual([{ t: "text", v: "bad" }]);
    expect(parseInline("[plain](http://example.com)")).toEqual([{ t: "text", v: "plain" }]);
    expect(safeHref("https://ok.edu/a b")).toBeNull();
    expect(safeHref(" https://ok.edu/a ")).toBe("https://ok.edu/a");
  });

  it("parses blocks: lists, quotes, code fences, rules; headings stay text", () => {
    const blocks = parseBlocks("# Not a heading\n\n- one\n- two\n\n1. first\n2. second\n\n> quoted\n\n```\nx = 1\n```\n\n---");
    expect(blocks.map((b) => b.t)).toEqual(["p", "ul", "ol", "quote", "pre", "hr"]);
    expect(blocks[0]).toEqual({ t: "p", c: [{ t: "text", v: "# Not a heading" }] });
    expect(blocks[1]).toMatchObject({ t: "ul", items: [[{ t: "p" }], [{ t: "p" }]] });
    expect(blocks[4]).toEqual({ t: "pre", v: "x = 1" });
    expect(parseBlocks("3. three\n4. four")[0]).toMatchObject({ t: "ol", start: 3 });
  });

  it("renders React elements, never raw HTML", () => {
    const { container } = render(
      <MarkdownPreview source={'<script>alert(1)</script> <img src=x onerror=alert(1)> **ok** ![pic](https://x.org/a.png)'} />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("strong")?.textContent).toBe("ok");
    expect(container.textContent).toContain("<script>alert(1)</script>");
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("https://x.org/a.png");
    expect(link?.getAttribute("rel")).toContain("noopener");
  });

  it("says when there is nothing to preview", () => {
    const { container } = render(<MarkdownPreview source="   " />);
    expect(container.textContent).toBe("Nothing to preview yet.");
  });
});

describe("course mentions", () => {
  it("detects a subject and digits before the caret", () => {
    expect(findMention("Is CMSC 1", 9)).toEqual({ start: 3, end: 9, query: "CMSC 1" });
    expect(findMention("math 15", 7)).toEqual({ start: 0, end: 7, query: "MATH 15" });
    expect(findMention("(econ20", 7)).toEqual({ start: 1, end: 7, query: "ECON 20" });
    expect(findMention("took CMSC 14100 and", 15)?.query).toBe("CMSC 14100");
  });

  it("ignores ordinary words, code spans, links and words in progress", () => {
    expect(findMention("about 3", 7)).toBeNull();
    expect(findMention("in 2", 4)).toBeNull(); // two letters
    expect(findMention("see `cmsc 1", 11)).toBeNull();
    expect(findMention("[x](https://a.edu/cmsc 1", 24)).toBeNull();
    expect(findMention("abcCMSC 1", 9)).toBeNull();
    expect(findMention("CMSC 1x", 6)).toBeNull();
    expect(findMention("CMSC", 4)).toBeNull();
  });

  it("inserts the canonical code", () => {
    const text = "Is cmsc 14 hard?";
    const m = findMention(text, 10);
    expect(m).not.toBeNull();
    const out = applyMention(text, m!, "CMSC 14100");
    expect(out.text).toBe("Is CMSC 14100 hard?");
    expect(out.caret).toBe(14);
    const end = applyMention("math 15", findMention("math 15", 7)!, "MATH 15300");
    expect(end).toEqual({ text: "MATH 15300 ", caret: 11 });
  });
});

describe("toolbar formatting", () => {
  it("wraps and unwraps the selection", () => {
    expect(applyFormat("make this bold", 5, 9, "bold")).toEqual({ text: "make **this** bold", selStart: 7, selEnd: 11 });
    expect(applyFormat("make **this** bold", 7, 11, "bold")).toEqual({ text: "make this bold", selStart: 5, selEnd: 9 });
    expect(applyFormat("x", 1, 1, "italic")).toEqual({ text: "x_italic text_", selStart: 2, selEnd: 13 });
    expect(applyFormat("word ", 0, 5, "code")).toEqual({ text: "`word` ", selStart: 1, selEnd: 5 });
  });

  it("makes links with the URL selected", () => {
    const out = applyFormat("see the guide", 8, 13, "link");
    expect(out.text).toBe("see the [guide](https://)");
    expect(out.text.slice(out.selStart, out.selEnd)).toBe("https://");
  });

  it("prefixes lines and takes the prefix back", () => {
    const listed = applyFormat("one\ntwo", 0, 7, "bullets");
    expect(listed.text).toBe("- one\n- two");
    expect(applyFormat(listed.text, 0, listed.text.length, "bullets").text).toBe("one\ntwo");
    expect(applyFormat("a\nb", 0, 3, "numbers").text).toBe("1. a\n2. b");
    expect(applyFormat("intro\nquote me", 8, 8, "quote").text).toBe("intro\n> quote me");
    expect(applyFormat("x\ny\n", 0, 4, "code").text).toBe("```\nx\ny\n```");
  });
});

describe("helpers", () => {
  it("finds search terms for similar questions", () => {
    expect(searchTerms("Is CMSC 14100 OK with no programming background?")).toEqual(["CMSC 14100", "programming", "background"]);
    expect(searchTerms("How do people fit study abroad with an Econ major?")).toEqual(["abroad", "study"]);
  });

  it("knows a summons, tags and day words", () => {
    expect(summonsBot("hey @quarterly")).toBe(true);
    expect(summonsBot("x@ai.com")).toBe(false);
    expect(toTag(" Study Abroad! ")).toBe("study-abroad");
    const today = new Date(2026, 10, 20);
    expect(dayWords("2026-11-20", today)).toBe("today");
    expect(dayWords("2026-11-19", today)).toBe("yesterday");
    expect(dayWords("2026-11-10", today)).toBe("last week");
    expect(dayWords("2026-09-01", today)).toBe("2 months ago");
  });
});

describe("Commons pages (mock API)", () => {
  afterEach(() => resetCommonsMock());

  it("lists questions to logged-out readers", async () => {
    renderRoute("/forum");
    const title = await screen.findByText(/is TEST 10000 fine without background/);
    expect(title.closest("a")).toHaveAttribute("href", "/forum/t/1");
    expect(screen.getByText("Hot").closest("[role=tab]")).toHaveAttribute("aria-selected", "true");
    expect(screen.getAllByText("AI answered").length).toBeGreaterThan(0);
  });

  it("shows a thread with the AI's answer, its sources and the reply tree", async () => {
    renderRoute("/forum/t/1");
    expect((await screen.findByText(/is TEST 10000 fine/, { selector: "h1" })).tagName).toBe("H1");
    expect(await screen.findByText("Fake AI answer: TEST 10000 has no prerequisite.")).toBeInTheDocument();
    expect(screen.getAllByText(/Written by an AI and can be wrong/).length).toBeGreaterThan(0);
    expect(screen.getByText("TEST 10000 · Fake Introduction I").closest("a")).toHaveAttribute("href", "/courses/TEST%2010000");
    expect(screen.getByText("Fake nested reply.")).toBeInTheDocument();
    expect(screen.getByText(/Log in to answer/)).toBeInTheDocument();
  });

  it("starts the bot on a pending question and shows its answer", async () => {
    renderRoute("/forum/t/2");
    expect(await screen.findByText(/Fake AI answer about FAKE 11000/)).toBeInTheDocument();
  });
});
