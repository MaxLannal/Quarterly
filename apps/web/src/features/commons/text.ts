/**
 * Text helpers of the Commons composer: course-mention detection at the caret, the toolbar's
 * markdown formatting, and the keywords used to find similar questions. Pure functions (tested
 * in commons.test.ts).
 */

/** Words that look like "SUBJ 1" but are not course subjects. */
const NOT_SUBJECTS = new Set([
  "and", "are", "but", "for", "had", "has", "how", "the", "was", "you", "not", "all", "any",
  "can", "our", "out", "see", "top", "two", "one", "per", "via", "with", "from", "year", "years",
  "week", "weeks", "take", "took", "than", "then", "into", "about", "over", "after", "under",
  "page", "part", "unit", "units", "hour", "hours", "grade", "level", "room", "class", "only",
  "just", "like", "maybe", "least", "most", "around", "since", "until", "spent", "need", "get",
  "got", "day", "days", "those", "these", "every", "each", "some", "more", "less", "first",
  "last", "next", "plus", "minus", "times", "number", "chapter", "lecture", "pset", "psets",
]);

export interface Mention {
  /** Where the typed code starts and ends in the text. */
  start: number;
  end: number;
  /** "CMSC 1", "MATH 15": the query for GET /courses?q=. */
  query: string;
}

/**
 * A course code being typed just before the caret: a subject of 3-5 letters and 1-5 digits
 * ("CMSC 1", "math 15", "econ20"), at the start of the text or after a space or punctuation.
 */
export function findMention(text: string, caret: number): Mention | null {
  const before = text.slice(0, caret);
  const match = /(^|[\s([{"'“‘,;:/])([A-Za-z]{3,5}) ?(\d{1,5})$/.exec(before);
  if (!match) return null;
  const subject = (match[2] as string).toUpperCase();
  if (NOT_SUBJECTS.has(subject.toLowerCase())) return null;
  // Inside an inline code span or a link target: leave it alone.
  const line = before.slice(before.lastIndexOf("\n") + 1);
  if ((line.match(/`/g) ?? []).length % 2 === 1 || /\]\([^)]*$/.test(line)) return null;
  const after = text.slice(caret, caret + 1);
  if (/[A-Za-z0-9]/.test(after)) return null; // the caret is inside a longer word
  const start = before.length - (match[0].length - (match[1] as string).length);
  return { start, end: caret, query: `${subject} ${match[3]}` };
}

/** `text` with the mention replaced by the canonical code (and a space after it). */
export function applyMention(text: string, mention: Mention, code: string): { text: string; caret: number } {
  const after = text.slice(mention.end);
  const spacer = after.startsWith(" ") || after.startsWith("\n") ? "" : " ";
  const next = text.slice(0, mention.start) + code + spacer + after;
  return { text: next, caret: mention.start + code.length + (after.startsWith("\n") ? 0 : 1) };
}

export type FormatKind = "bold" | "italic" | "code" | "link" | "quote" | "bullets" | "numbers";

export interface Edit {
  text: string;
  selStart: number;
  selEnd: number;
}

const WRAP: Record<"bold" | "italic" | "code", string> = { bold: "**", italic: "_", code: "`" };

function lineRange(text: string, start: number, end: number): [number, number] {
  const from = text.lastIndexOf("\n", start - 1) + 1;
  const nl = text.indexOf("\n", end > start && text[end - 1] === "\n" ? end - 1 : end);
  return [from, nl === -1 ? text.length : nl];
}

/**
 * The toolbar's formatting on the selection `[start, end)`: wrap it (bold, italic, code, link:
 * pressing again unwraps) or prefix its lines (quote, bullets, numbers). The new selection
 * covers the same words, or the placeholder to type over.
 */
export function applyFormat(text: string, start: number, end: number, kind: FormatKind): Edit {
  const selected = text.slice(start, end);
  if (kind === "bold" || kind === "italic" || kind === "code") {
    if (kind === "code" && selected.includes("\n")) {
      const block = "```\n" + selected.replace(/\n$/, "") + "\n```";
      const lead = start > 0 && text[start - 1] !== "\n" ? "\n" : "";
      const out = text.slice(0, start) + lead + block + text.slice(end);
      const s = start + lead.length + 4;
      return { text: out, selStart: s, selEnd: s + selected.replace(/\n$/, "").length };
    }
    const mark = WRAP[kind];
    const n = mark.length;
    if (text.slice(start - n, start) === mark && text.slice(end, end + n) === mark) {
      const out = text.slice(0, start - n) + selected + text.slice(end + n);
      return { text: out, selStart: start - n, selEnd: end - n };
    }
    if (selected.length > 2 * n && selected.startsWith(mark) && selected.endsWith(mark)) {
      const inner = selected.slice(n, -n);
      return { text: text.slice(0, start) + inner + text.slice(end), selStart: start, selEnd: start + inner.length };
    }
    const placeholder = kind === "bold" ? "bold text" : kind === "italic" ? "italic text" : "code";
    // Keep spaces around the selection outside the markers ("**word** " not "**word **").
    const body = selected.trim() || placeholder;
    const leadSpace = selected.length - selected.trimStart().length;
    const trailSpace = selected.trim() ? selected.length - selected.trimEnd().length : 0;
    const out =
      text.slice(0, start) + " ".repeat(leadSpace) + mark + body + mark + " ".repeat(trailSpace) + text.slice(end);
    const s = start + leadSpace + n;
    return { text: out, selStart: s, selEnd: s + body.length };
  }
  if (kind === "link") {
    const label = selected.trim() || "link text";
    const looksLikeUrl = /^https?:\/\/\S+$/.test(selected.trim());
    if (looksLikeUrl) {
      const out = text.slice(0, start) + `[link text](${selected.trim()})` + text.slice(end);
      return { text: out, selStart: start + 1, selEnd: start + 10 };
    }
    const out = text.slice(0, start) + `[${label}](https://)` + text.slice(end);
    const urlAt = start + label.length + 3;
    return { text: out, selStart: urlAt, selEnd: urlAt + 8 };
  }
  // Line prefixes.
  const [from, to] = lineRange(text, start, end);
  const lines = text.slice(from, to).split("\n");
  const pattern = kind === "quote" ? /^> ?/ : kind === "bullets" ? /^[-*+] / : /^\d+[.)] /;
  const all = lines.every((l) => !l.trim() || pattern.test(l));
  const next = lines.map((l, i) => {
    if (all) return l.replace(pattern, "");
    if (!l.trim() && lines.length > 1) return l;
    const bare = l.replace(/^(> ?|[-*+] |\d+[.)] )/, "");
    return (kind === "quote" ? "> " : kind === "bullets" ? "- " : `${i + 1}. `) + bare;
  });
  const replaced = next.join("\n");
  const out = text.slice(0, from) + replaced + text.slice(to);
  if (start === end && !all) {
    const caret = from + replaced.length;
    return { text: out, selStart: caret, selEnd: caret };
  }
  return { text: out, selStart: from, selEnd: from + replaced.length };
}

const STOP = new Set(
  (
    "a an and are as at be been best but by can could do does doing for from get good has have how " +
    "i if im i'm in into is it its just me more most my no not of on or other people should so " +
    "some take taking than that the their them then there these they this to too very want was " +
    "we what when where which who why will with would you your about any anyone ok okay vs really " +
    "course courses class classes uchicago chicago"
  ).split(" "),
);

/** The words of a question that say what it is about (for "Already asked?"): a course code
 * first when there is one, then the longest content words. */
export function searchTerms(title: string, max = 2): string[] {
  const code = /\b([A-Za-z]{3,5}) ?(\d{5})\b/.exec(title);
  const out: string[] = [];
  if (code) out.push(`${(code[1] as string).toUpperCase()} ${code[2]}`);
  const words = (title.toLowerCase().match(/[a-z][a-z'-]{3,}/g) ?? [])
    .map((w) => w.replace(/'s$/, ""))
    .filter((w) => !STOP.has(w) && !(code && w === (code[1] as string).toLowerCase()));
  const unique = [...new Set(words)].sort((a, b) => b.length - a.length);
  for (const w of unique) {
    if (out.length >= max + (code ? 1 : 0)) break;
    out.push(w);
  }
  return out;
}

/** Does a reply ask the bot to join (the server decides too)? */
export function summonsBot(text: string): boolean {
  return /(^|[^\w@])@(quarterly|ai)\b/i.test(text);
}

/** "today", "yesterday", "3 days ago", "2 weeks ago": day-level only. */
export function dayWords(day: string, today: Date = new Date()): string {
  const [y, mo, d] = day.split("-").map(Number);
  if (!y || !mo || !d) return day;
  const then = Date.UTC(y, mo - 1, d);
  const now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.round((now - then) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 30) {
    const w = Math.floor(days / 7);
    return w === 1 ? "last week" : `${w} weeks ago`;
  }
  if (days < 365) {
    const m = Math.floor(days / 30);
    return m === 1 ? "last month" : `${m} months ago`;
  }
  const yrs = Math.floor(days / 365);
  return yrs === 1 ? "last year" : `${yrs} years ago`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** Tags as the server stores them: lowercase slugs of at most 24 characters. */
export function toTag(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/^-+|-+$/g, "")
    .slice(0, 24);
}

export function coursePath(code: string): string {
  return `/courses/${encodeURIComponent(code)}`;
}

export function threadPath(id: number, replyId?: number): string {
  return `/forum/t/${id}${replyId ? `#reply-${replyId}` : ""}`;
}
