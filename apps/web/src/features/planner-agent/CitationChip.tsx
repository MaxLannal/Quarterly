/** Citation chips for planner answers and proposals (moved from the advisor panel, prompt 07). */
import { Link } from "react-router-dom";
import type { Citation } from "@/api/types";
import { useSession } from "@/features/auth/session";
import { useForumPageById, usePost } from "@/features/forum/api";
import { pagePath, threadPath } from "@/features/forum/format";

// Citation chip: a 32px neutral pill drawn inside a transparent 6px border, so links keep a 44px
// target (same technique as Button size "sm"). Tabular Inter: course codes never use the serif.
const chipClass =
  "inline-flex min-h-11 items-center rounded-pill border-[6px] border-transparent bg-surface-strong bg-clip-padding px-3 text-caption tabular-nums text-ink";
// D11 AD-3: a linked chip is told apart by its maroon text, not an underline inside a pill.
const chipLinkClass = `${chipClass} text-primary hover:bg-hairline hover:text-primary-hover focus-visible:outline-offset-[-4px]`;

/** "workload 13 h/wk · n=34" reads as "Workload 13 h/wk (34 ratings)" (D11 AD-3). */
export function chipLabel(label: string): string {
  const t = label.replace(/\s*·\s*n=(\d+)/, (_, n: string) => ` (${n} rating${n === "1" ? "" : "s"})`);
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function ChipLink({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} className={chipLinkClass}>
      {chipLabel(label)}
    </Link>
  );
}

/**
 * A forum citation (`post:POST_ID` or `summary:PAGE_ID`). The id alone cannot build the URL
 * (`/courses/:code/i/:instructor/t/:id`), so the chip asks the API for the post (which names its
 * page) and the page (which names the course and instructor). Forum reads need a login, so a
 * logged-out student, a removed post or a failed request keeps a plain chip: same pill, no
 * underline, nothing to click.
 */
function ForumCitationChip({ c }: { c: Citation }) {
  const session = useSession();
  const loggedIn = session.status === "authenticated";
  const isPost = c.kind === "post";
  const post = usePost(isPost ? Number(c.id) : Number.NaN, loggedIn && isPost);
  const pageId = isPost ? post.data?.page_id : Number(c.id);
  const page = useForumPageById(pageId ?? Number.NaN, loggedIn && pageId != null);
  if (page.data) {
    const { course_code: code, instructor } = page.data;
    return <ChipLink to={isPost ? threadPath(code, instructor.slug, Number(c.id)) : pagePath(code, instructor.slug)} label={c.label} />;
  }
  return <span className={chipClass}>{chipLabel(c.label)}</span>;
}

export function CitationChip({ c, rules }: { c: Citation; rules?: ReadonlyMap<string, string> }) {
  // Issue #17: a field of the student's record links to it on the dashboard; a guideline rule
  // shows its text on hover and to screen readers.
  if (c.kind === "profile") return <ChipLink to={`/me#field-${encodeURIComponent(c.id)}`} label={c.label} />;
  if (c.kind === "guideline") {
    const text = rules?.get(c.id);
    return (
      <span className={chipClass} title={text}>
        {chipLabel(c.label)}
        {text && <span className="sr-only">: {text}</span>}
      </span>
    );
  }
  if (c.kind === "course") return <ChipLink to={`/courses/${encodeURIComponent(c.id)}`} label={c.label} />;
  if (c.kind === "program") return <ChipLink to={`/programs/${encodeURIComponent(c.id)}`} label={c.label} />;
  if (c.kind === "attribute") {
    // `CODE:key` (for example "CMSC 14300:workload_hours"): the attribute is shown on the course page.
    const code = c.id.slice(0, c.id.lastIndexOf(":"));
    if (code) return <ChipLink to={`/courses/${encodeURIComponent(code)}`} label={c.label} />;
  }
  if (c.kind === "post" || c.kind === "summary") return <ForumCitationChip c={c} />;
  return <span className={chipClass}>{chipLabel(c.label)}</span>;
}

