import type { Issue } from "@/api/types";

/**
 * Short forms of the verifier's issues (FEEDBACK "Concatenating Error Messages", 2026-11-16):
 * show the essential point, and keep the full message one click away ("Details").
 *
 * - `card`: on a course card, which already shows the course and its quarter
 *   ("Prerequisite not met.").
 * - `list`: in the plan check ("Prerequisite of MATH 20250 not met.").
 * - `link`: where the details live, when there is such a place (the course's prerequisites).
 */
export interface IssueSummary {
  card: string;
  list: string;
  link?: { label: string; href: string };
}

const TERM = /\s+in\s+\d{4}-(AU|WI|SP|SU)\b/g;
const QUARTER = /\b(\d{4})-(AU|WI|SP|SU)\b/g;
const QUARTER_NAMES: Record<string, string> = { AU: "Autumn", WI: "Winter", SP: "Spring", SU: "Summer" };

/** "2027-SU" -> "Summer 2027", everywhere in a sentence. */
function readableTerms(text: string): string {
  return text.replace(QUARTER, (_, year: string, q: string) => `${QUARTER_NAMES[q]} ${year}`);
}

/** The message up to its first colon, semicolon or sentence end, without the full stop. */
export function firstClause(message: string): string {
  const cut = message.search(/[:;]|\.\s/);
  const head = cut > 0 ? message.slice(0, cut) : message;
  return head.replace(/\.\s*$/, "").trim();
}

function sentence(text: string): string {
  const t = text.trim();
  return t ? `${t.charAt(0).toUpperCase()}${t.slice(1)}${/[.?!]$/.test(t) ? "" : "."}` : t;
}

export function coursePageHref(code: string, section?: string): string {
  return `/courses/${encodeURIComponent(code)}${section ? `#${section}` : ""}`;
}

export function summarizeIssue(issue: Issue): IssueSummary {
  const message = issue.message;
  const course = issue.course_ids?.[0];

  if (issue.code === "V03" && course) {
    const consent = /needs the consent of the (.+?)\.?$/.exec(message);
    if (consent) {
      return {
        card: `Needs the ${consent[1]}'s consent.`,
        list: `${course} needs the ${consent[1]}'s consent.`,
      };
    }
    const kind = /^(Prerequisite|Co-requisite|Restriction)/.exec(message)?.[1] ?? "Prerequisite";
    return {
      card: `${kind} not met.`,
      list: `${kind} of ${course} not met.`,
      link: { label: `View ${kind === "Restriction" ? "restriction" : kind.toLowerCase()}`, href: coursePageHref(course, "prereq") },
    };
  }

  if (issue.code === "V01" && course && /is not in the .* catalog/.test(message)) {
    return { card: "Not in this catalog year.", list: `${course} is not in this catalog year.` };
  }

  if (issue.code === "V04" && course) {
    const usual = /is not usually offered in (Autumn|Winter|Spring|Summer)/.exec(message);
    const short = usual ? `Not usually offered in ${usual[1]}.` : "Not on the posted schedule.";
    return { card: short, list: `${course}: ${short.charAt(0).toLowerCase()}${short.slice(1)}`, link: { label: "View offerings", href: coursePageHref(course, "offer") } };
  }

  if (issue.code === "V06" && (issue.course_ids ?? []).length >= 2) {
    const [a, b] = issue.course_ids ?? [];
    return { card: "Time conflict.", list: `${a} and ${b} meet at the same time.` };
  }

  // Everything else: the first clause, with term ids made readable.
  const head = readableTerms(firstClause(message));
  const cardText = course ? head.replace(new RegExp(`^${course}\\s*`), "").replace(TERM, "") : head;
  return { card: sentence(cardText || head), list: sentence(head) };
}

/** True when the short form leaves something out, so "Details" is worth offering. */
export function hasDetails(issue: Issue): boolean {
  const s = summarizeIssue(issue);
  return s.list.replace(/\.$/, "") !== issue.message.replace(/\.$/, "") || (issue.fix_hints ?? []).length > 0;
}
