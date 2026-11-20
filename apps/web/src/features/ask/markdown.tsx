/**
 * A safe renderer for the markdown subset the campus guide writes: paragraphs, `-` / `1.` lists,
 * **bold**, *italic*, `code` and [links](/path). It builds React elements (no HTML strings, no
 * dangerouslySetInnerHTML), so nothing in an answer can inject markup. Links: a path on this site
 * becomes a router `Link`; an https link to uchicago.edu opens in a new tab; anything else stays
 * plain text. Course codes the API confirmed (`courses`) become links to their course pages.
 */
import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { inlineLinkClass } from "@/components/layout/page";

export type Block =
  | { kind: "p"; text: string }
  | { kind: "ul" | "ol"; items: string[] };

const BULLET = /^\s*(?:[-*•])\s+(.*)$/;
const NUMBERED = /^\s*\d{1,2}[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

/** Splits text into paragraphs and lists. A heading line reads as a bold paragraph. */
export function blocksOf(source: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: { kind: "ul" | "ol"; items: string[] } | null = null;
  const flushPara = () => {
    if (para.length) blocks.push({ kind: "p", text: para.join("\n") });
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };
  for (const raw of source.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.replace(/\s+$/, "");
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    const heading = HEADING.exec(line);
    if (bullet || numbered) {
      flushPara();
      const kind = bullet ? "ul" : "ol";
      if (!list || list.kind !== kind) {
        flushList();
        list = { kind, items: [] };
      }
      list.items.push(((bullet ?? numbered) as RegExpExecArray)[1] ?? "");
    } else if (!line.trim()) {
      flushPara();
      flushList();
    } else if (heading) {
      flushPara();
      flushList();
      blocks.push({ kind: "p", text: `**${(heading[1] ?? "").replace(/\*\*/g, "")}**` });
    } else if (list && /^\s{2,}\S/.test(raw)) {
      // An indented line continues the last list item.
      list.items[list.items.length - 1] += " " + line.trim();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return blocks;
}

/** A path on this site ("/courses/X"), never "//host" or one with a backslash. */
export function isInternalPath(href: string): boolean {
  return /^\/(?!\/)/.test(href) && !/[\\\s]/.test(href);
}

/** An https page on uchicago.edu (the only external links an answer may carry). */
export function isTrustedExternal(href: string): boolean {
  try {
    const url = new URL(href);
    const host = url.hostname.toLowerCase();
    return url.protocol === "https:" && (host === "uchicago.edu" || host.endsWith(".uchicago.edu"));
  } catch {
    return false;
  }
}

const COURSE = /\b([A-Z]{2,5}) ?(\d{5})\b/g;
const INLINE = /(\*\*([^*]+?)\*\*)|(`([^`]+)`)|(\[([^\]\n]+)\]\(([^)\s]+)\))|(\*([^*\s][^*\n]*?)\*)|(\b_([^_\n]+?)_\b)/g;

export function courseHref(code: string): string {
  return `/courses/${encodeURIComponent(code)}`;
}

interface Ctx {
  courses: ReadonlySet<string>;
  key: { n: number };
  /** Called when the reader follows a link (the companion closes itself). */
  onNavigate?: () => void;
}

function withCourses(text: string, ctx: Ctx): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(COURSE)) {
    const code = `${match[1]} ${match[2]}`;
    if (!ctx.courses.has(code)) continue;
    const at = match.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    out.push(
      <Link
        key={`c${ctx.key.n++}`}
        to={courseHref(code)}
        onClick={ctx.onNavigate}
        className="whitespace-nowrap rounded-xs font-medium text-primary underline decoration-primary/30 underline-offset-[3px] hover:decoration-primary"
      >
        {match[0]}
      </Link>,
    );
    last = at + match[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function plainWithBreaks(text: string, ctx: Ctx): ReactNode[] {
  const lines = text.split("\n");
  return lines.flatMap((line, i) => {
    const parts = withCourses(line, ctx);
    return i < lines.length - 1 ? [...parts, <br key={`br${ctx.key.n++}`} />] : parts;
  });
}

function link(label: string, href: string, ctx: Ctx): ReactNode {
  const children = inline(label, ctx, false);
  if (isInternalPath(href)) {
    return (
      <Link key={`l${ctx.key.n++}`} to={href} onClick={ctx.onNavigate} className={inlineLinkClass}>
        {children}
      </Link>
    );
  }
  if (isTrustedExternal(href)) {
    return (
      <a key={`l${ctx.key.n++}`} href={href} target="_blank" rel="noopener noreferrer" className={inlineLinkClass}>
        {children}
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
    );
  }
  return <Fragment key={`l${ctx.key.n++}`}>{children}</Fragment>;
}

/** Inline markdown as React nodes. `links` is false inside a link's own label. */
export function inline(text: string, ctx: Ctx, links = true): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    const at = m.index ?? 0;
    if (m[5] && !links) continue;
    if (at > last) out.push(...plainWithBreaks(text.slice(last, at), ctx));
    if (m[1]) out.push(<strong key={`b${ctx.key.n++}`} className="font-semibold text-ink">{inline(m[2] ?? "", ctx, links)}</strong>);
    else if (m[3]) out.push(<code key={`k${ctx.key.n++}`} className="rounded-xs bg-surface-strong px-1 py-0.5 font-mono text-[0.9em] text-body-strong">{m[4]}</code>);
    else if (m[5]) out.push(link(m[6] ?? "", m[7] ?? "", ctx));
    else if (m[8]) out.push(<em key={`i${ctx.key.n++}`}>{inline(m[9] ?? "", ctx, links)}</em>);
    else if (m[10]) out.push(<em key={`i${ctx.key.n++}`}>{inline(m[11] ?? "", ctx, links)}</em>);
    last = at + m[0].length;
  }
  if (last < text.length) out.push(...plainWithBreaks(text.slice(last), ctx));
  return out;
}

export function Markdown({
  text,
  courses = [],
  onNavigate,
  className,
}: {
  text: string;
  /** Course codes the API confirmed exist; only these become course links. */
  courses?: readonly string[];
  onNavigate?: () => void;
  className?: string;
}) {
  const ctx: Ctx = { courses: new Set(courses), key: { n: 0 }, onNavigate };
  return (
    <div className={className}>
      {blocksOf(text).map((block, i) => {
        if (block.kind === "p") {
          return (
            <p key={i} className="[&:not(:first-child)]:mt-3">
              {inline(block.text, ctx)}
            </p>
          );
        }
        const List = block.kind;
        return (
          <List
            key={i}
            className={
              (block.kind === "ul" ? "list-disc marker:text-primary/60" : "list-decimal marker:text-muted") +
              " ms-5 flex flex-col gap-1.5 [&:not(:first-child)]:mt-3"
            }
          >
            {block.items.map((item, j) => (
              <li key={j} className="ps-1">
                {inline(item, ctx)}
              </li>
            ))}
          </List>
        );
      })}
    </div>
  );
}
