import type { AskContext } from "@/features/ask/types";

/** Where the student is, read from the path: the companion sends it with each question. */
export function contextOf(pathname: string): AskContext {
  const context: AskContext = { page: pathname.slice(0, 200) };
  const course = /^\/courses\/([^/]+)/.exec(pathname);
  if (course?.[1]) {
    let code = course[1];
    try {
      code = decodeURIComponent(code);
    } catch {
      // keep it as written
    }
    code = code.replace(/\s+/g, " ").trim().toUpperCase();
    if (/^[A-Z]{2,5} ?\d{5}$/.test(code)) context.course_code = code.slice(0, 16);
  }
  const thread = /^\/forum\/t\/(\d{1,12})(?:\/|$)/.exec(pathname);
  if (thread?.[1]) context.thread_id = Number(thread[1]);
  return context;
}

/** The companion's first line and three questions to start with, for the page it is on. */
export function suggestionsFor(context: AskContext): { lead: string; chips: string[] } {
  const page = context.page ?? "/";
  const code = context.course_code;
  if (code) {
    return {
      lead: `Looking at ${code}? I can tell you how it fits you and what students say.`,
      chips: [`Is ${code} a good fit for me?`, `What do students say about ${code}?`, `What should I take after ${code}?`],
    };
  }
  if (context.thread_id) {
    return {
      lead: "Reading a forum question? I can add what the catalog and the campus guide say.",
      chips: ["What does the catalog say about this?", "Which courses relate to this question?", "Who should I ask about this on campus?"],
    };
  }
  if (page.startsWith("/forum")) {
    return {
      lead: "Before you post, I can check what students already asked.",
      chips: ["What are students asking about the Core?", "Has anyone asked about first-year math?", "How do I choose a Humanities sequence?"],
    };
  }
  if (page.startsWith("/feed")) {
    return {
      lead: "I can explain why a course is in your feed or find more like it.",
      chips: ["Find me a fun course outside my major", "Which arts courses count for the Core?", "What's a good light course this quarter?"],
    };
  }
  if (page.startsWith("/me")) {
    return {
      lead: "I can talk through your routes and what to take next.",
      chips: ["Which of my routes fits me best?", "What should I take next quarter?", "How can I start research in my field?"],
    };
  }
  if (page.startsWith("/plan")) {
    return {
      lead: "Planning quarters? Ask me about the Core, loads and when courses run.",
      chips: ["How heavy is a four-course quarter?", "Which Core courses fit Autumn?", "How do I fit a quarter abroad in?"],
    };
  }
  if (page.startsWith("/programs")) {
    return {
      lead: "Comparing majors and minors? I can read their requirements with you.",
      chips: ["What's the difference between the CS BA and BS?", "Which courses start the economics major?", "Can I double major in math and CS?"],
    };
  }
  return {
    lead: "Ask me anything about courses, the Core or life in the College.",
    chips: ["What should a first-year take in Autumn?", "How does the Core work?", "Where do students study on campus?"],
  };
}
