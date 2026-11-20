/**
 * A safe client-side renderer for the Commons composer's Preview tab: a small markdown subset
 * parsed into a tree and rendered as React elements (never as HTML strings), matching what the
 * server allows (api/forum/markdown.py): paragraphs with line breaks, **strong**, _em_,
 * ~~strike~~, `code`, fenced code blocks, > quotes, - and 1. lists, --- rules and links to
 * https URLs only. No raw HTML, no headings (a "#" line stays text), no images.
 */
import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type Inline =
  | { t: "text"; v: string }
  | { t: "strong" | "em" | "del"; c: Inline[] }
  | { t: "code"; v: string }
  | { t: "a"; href: string; c: Inline[] }
  | { t: "br" };

export type Block =
  | { t: "p"; c: Inline[] }
  | { t: "pre"; v: string }
  | { t: "quote"; c: Block[] }
  | { t: "ul"; items: Block[][] }
  | { t: "ol"; start: number; items: Block[][] }
  | { t: "hr" };

const PUNCT = /[\\`*_{}[\]()#+\-.!~>|]/;

/** A link target the preview may render: absolute https only. */
export function safeHref(raw: string): string | null {
  const href = raw.trim();
  if (!/^https:\/\/[^\s<>"]+$/i.test(href)) return null;
  try {
    const url = new URL(href);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function pushText(out: Inline[], text: string) {
  if (!text) return;
  const last = out[out.length - 1];
  if (last && last.t === "text") last.v += text;
  else out.push({ t: "text", v: text });
}

/** Where the closing `delim` of a span opened at `from` is, or -1. */
function closing(src: string, delim: string, from: number): number {
  let i = from;
  while (i < src.length) {
    if (src[i] === "\\") {
      i += 2;
      continue;
    }
    if (src[i] === "`") {
      // Code spans are opaque: skip over them.
      const end = src.indexOf("`", i + 1);
      if (end === -1) return -1;
      i = end + 1;
      continue;
    }
    if (src.startsWith(delim, i) && i > from && !/\s/.test(src[i - 1] ?? "")) {
      // A single * or _ must not be the start of a double one.
      if (delim.length === 1 && src[i + 1] === delim) {
        i += 2;
        continue;
      }
      if (delim === "_" && /[A-Za-z0-9]/.test(src[i + 1] ?? "")) {
        i += 1;
        continue;
      }
      return i;
    }
    i += 1;
  }
  return -1;
}

/** The index of the ")" that closes the "(" at `open` (nested pairs allowed), or -1. */
function matchingParen(src: string, open: number): number {
  let depth = 0;
  for (let i = open; i < src.length; i += 1) {
    if (src[i] === "(") depth += 1;
    else if (src[i] === ")" && --depth === 0) return i;
    else if (src[i] === "\n") return -1;
  }
  return -1;
}

/** The inline content of one paragraph (newlines become line breaks). */
export function parseInline(src: string, depth = 0): Inline[] {
  const out: Inline[] = [];
  let i = 0;
  while (i < src.length) {
    const ch = src[i] as string;
    const next = src[i + 1] ?? "";
    if (ch === "\\" && PUNCT.test(next)) {
      pushText(out, next);
      i += 2;
      continue;
    }
    if (ch === "\n") {
      out.push({ t: "br" });
      i += 1;
      continue;
    }
    if (ch === "`") {
      let ticks = 1;
      while (src[i + ticks] === "`") ticks += 1;
      const fence = "`".repeat(ticks);
      const end = src.indexOf(fence, i + ticks);
      if (end > i + ticks - 1) {
        const code = src.slice(i + ticks, end).replace(/\n/g, " ");
        out.push({ t: "code", v: code.length > 2 && code.startsWith(" ") && code.endsWith(" ") ? code.slice(1, -1) : code });
        i = end + ticks;
        continue;
      }
      pushText(out, fence);
      i += ticks;
      continue;
    }
    if (depth < 6) {
      const double = src.slice(i, i + 2);
      if ((double === "**" || double === "__" || double === "~~") && !/\s/.test(src[i + 2] ?? " ")) {
        const end = closing(src, double, i + 2);
        if (end > i + 2) {
          const kind = double === "~~" ? "del" : "strong";
          out.push({ t: kind, c: parseInline(src.slice(i + 2, end), depth + 1) });
          i = end + 2;
          continue;
        }
      }
      const intraword = ch === "_" && /[A-Za-z0-9]/.test(src[i - 1] ?? "");
      if ((ch === "*" || ch === "_") && !intraword && !/\s/.test(next || " ") && next !== ch) {
        const end = closing(src, ch, i + 1);
        if (end > i + 1) {
          out.push({ t: "em", c: parseInline(src.slice(i + 1, end), depth + 1) });
          i = end + 1;
          continue;
        }
      }
      if (ch === "[") {
        const close = src.indexOf("](", i + 1);
        const paren = close === -1 ? -1 : matchingParen(src, close + 1);
        if (close > i && paren > close && !src.slice(i + 1, close).includes("\n")) {
          const label = src.slice(i + 1, close);
          const href = safeHref(src.slice(close + 2, paren));
          const inner = parseInline(label, depth + 1);
          if (href) out.push({ t: "a", href, c: inner });
          else
            for (const part of inner) {
              if (part.t === "text") pushText(out, part.v);
              else out.push(part);
            }
          i = paren + 1;
          continue;
        }
      }
    }
    pushText(out, ch);
    i += 1;
  }
  return out;
}

const FENCE = /^ {0,3}(`{3,}|~{3,})/;
const BULLET = /^ {0,3}[-*+]\s+/;
const NUMBER = /^ {0,3}(\d{1,6})[.)]\s+/;
const QUOTE = /^ {0,3}>\s?/;
const RULE = /^ {0,3}([-*_])(\s*\1){2,}\s*$/;

/** The blocks of a markdown text. */
export function parseBlocks(src: string, depth = 0): Block[] {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ t: "p", c: parseInline(para.join("\n").trim(), 0) });
    para = [];
  };
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] as string;
    const fence = FENCE.exec(line);
    if (fence) {
      flush();
      const marker = (fence[1] as string).slice(0, 3);
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !(lines[i] as string).trimStart().startsWith(marker)) {
        body.push(lines[i] as string);
        i += 1;
      }
      blocks.push({ t: "pre", v: body.join("\n") });
      i += 1;
      continue;
    }
    if (!line.trim()) {
      flush();
      i += 1;
      continue;
    }
    if (RULE.test(line) && !para.length) {
      blocks.push({ t: "hr" });
      i += 1;
      continue;
    }
    if (QUOTE.test(line) && depth < 4) {
      flush();
      const inner: string[] = [];
      while (i < lines.length && QUOTE.test(lines[i] as string)) {
        inner.push((lines[i] as string).replace(QUOTE, ""));
        i += 1;
      }
      blocks.push({ t: "quote", c: parseBlocks(inner.join("\n"), depth + 1) });
      continue;
    }
    const bullet = BULLET.test(line);
    const number = NUMBER.exec(line);
    if ((bullet || number) && depth < 4) {
      flush();
      const ordered = !bullet;
      const pattern = ordered ? NUMBER : BULLET;
      const items: Block[][] = [];
      let current: string[] = [];
      while (i < lines.length) {
        const l = lines[i] as string;
        if (pattern.test(l)) {
          if (current.length) items.push(parseBlocks(current.join("\n"), depth + 1));
          current = [l.replace(pattern, "")];
        } else if (l.trim() && /^\s{2,}/.test(l)) {
          current.push(l.trim());
        } else if (l.trim() && !BULLET.test(l) && !NUMBER.test(l) && !QUOTE.test(l) && !FENCE.test(l)) {
          current.push(l.trim()); // a lazy continuation line
        } else {
          break;
        }
        i += 1;
      }
      if (current.length) items.push(parseBlocks(current.join("\n"), depth + 1));
      blocks.push(ordered ? { t: "ol", start: Number(number?.[1] ?? 1), items } : { t: "ul", items });
      continue;
    }
    para.push(line);
    i += 1;
  }
  flush();
  return blocks;
}

function renderInline(nodes: Inline[]): ReactNode[] {
  return nodes.map((n, i) => {
    switch (n.t) {
      case "text":
        return <Fragment key={i}>{n.v}</Fragment>;
      case "br":
        return <br key={i} />;
      case "code":
        return <code key={i}>{n.v}</code>;
      case "strong":
        return <strong key={i}>{renderInline(n.c)}</strong>;
      case "em":
        return <em key={i}>{renderInline(n.c)}</em>;
      case "del":
        return <del key={i}>{renderInline(n.c)}</del>;
      case "a":
        return (
          <a key={i} href={n.href} target="_blank" rel="nofollow noopener noreferrer ugc">
            {renderInline(n.c)}
          </a>
        );
    }
  });
}

function renderBlocks(blocks: Block[]): ReactNode[] {
  return blocks.map((b, i) => {
    switch (b.t) {
      case "p":
        return <p key={i}>{renderInline(b.c)}</p>;
      case "pre":
        return (
          <pre key={i}>
            <code>{b.v}</code>
          </pre>
        );
      case "quote":
        return <blockquote key={i}>{renderBlocks(b.c)}</blockquote>;
      case "hr":
        return <hr key={i} />;
      case "ul":
        return (
          <ul key={i}>
            {b.items.map((item, j) => (
              <li key={j}>{renderItem(item)}</li>
            ))}
          </ul>
        );
      case "ol":
        return (
          <ol key={i} start={b.start === 1 ? undefined : b.start}>
            {b.items.map((item, j) => (
              <li key={j}>{renderItem(item)}</li>
            ))}
          </ol>
        );
    }
  });
}

/** A list item that is one paragraph renders without the <p> (a tight list). */
function renderItem(blocks: Block[]): ReactNode {
  const [only] = blocks;
  if (blocks.length === 1 && only?.t === "p") return renderInline(only.c);
  return renderBlocks(blocks);
}

/** Prose styles shared by the preview and the server-rendered bodies. */
export const proseClass = cn(
  "text-body-md text-body [overflow-wrap:anywhere]",
  "[&_p]:mb-3 [&_p:last-child]:mb-0 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_li]:mb-1",
  "[&_a]:rounded-xs [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2 [&_a:hover]:text-primary-hover",
  "[&_a[data-course]]:font-medium [&_a[data-course]]:no-underline [&_a[data-course]]:decoration-primary/40 [&_a[data-course]:hover]:underline",
  "[&_blockquote]:mb-3 [&_blockquote]:border-l-2 [&_blockquote]:border-hairline-strong [&_blockquote]:pl-4 [&_blockquote]:text-muted",
  "[&_code]:rounded-xs [&_code]:bg-surface-strong [&_code]:px-1 [&_code]:font-mono [&_code]:text-caption [&_code]:text-ink",
  "[&_pre]:mb-3 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-surface-strong [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0",
  "[&_hr]:my-4 [&_hr]:border-hairline [&_strong]:font-semibold [&_strong]:text-ink",
);

export function MarkdownPreview({ source, className }: { source: string; className?: string }) {
  const blocks = parseBlocks(source);
  if (!blocks.length) return <p className={cn("text-body-sm text-muted", className)}>Nothing to preview yet.</p>;
  return <div className={cn(proseClass, className)}>{renderBlocks(blocks)}</div>;
}
