import { memo } from "react";
import { COVERS } from "./palette";
import { hash, rng } from "./rng";

/** Break a title into lines of at most `width` characters (whole words). */
export function wrap(text: string, width: number, maxLines: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(/\s+/)) {
    if (!word) continue;
    if ((line + " " + word).trim().length > width && line) {
      lines.push(line);
      line = word;
    } else {
      line = (line + " " + word).trim();
    }
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    kept[maxLines - 1] = `${kept[maxLines - 1]?.replace(/[,:;.]$/, "")}…`;
    return kept;
  }
  return lines;
}

/**
 * A generated book cover (no image is fetched): a ground colour from the title's hash, a spine,
 * a printer's ornament and the title and author set in type. Decorative: the card names the book.
 */
export const BookCover = memo(function BookCover({
  title,
  author,
  slug,
  size = "md",
  className,
}: {
  title: string;
  author: string;
  slug: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const h = hash(slug);
  const c = COVERS[h % COVERS.length]!;
  const r = rng(h);
  const ornament = Math.floor(r() * 4);
  const small = size === "sm";
  const lines = wrap(title.replace(/:.*$/, ""), small ? 11 : 13, small ? 3 : 4);
  const fontSize = small ? 13 : lines.some((l) => l.length > 11) ? 15 : 17;
  const top = small ? 46 : 64;
  return (
    <svg viewBox="0 0 120 180" className={className} aria-hidden="true" focusable="false">
      <rect width={120} height={180} rx={3} fill={c.ground} />
      <rect width={9} height={180} fill="var(--color-ink)" opacity={0.2} />
      <rect x={9} width={1.2} height={180} fill="var(--color-surface-card)" opacity={0.2} />
      {ornament === 0 && <circle cx={64} cy={small ? 26 : 34} r={small ? 9 : 13} fill="none" stroke={c.rule} strokeWidth={1.4} />}
      {ornament === 1 && (
        <g stroke={c.rule} strokeWidth={1.2}>
          <line x1={22} y1={small ? 24 : 30} x2={106} y2={small ? 24 : 30} />
          <line x1={22} y1={small ? 29 : 36} x2={106} y2={small ? 29 : 36} />
        </g>
      )}
      {ornament === 2 && <path d={`M64,${small ? 16 : 22} l9,9 l-9,9 l-9,-9 z`} fill={c.rule} opacity={0.9} />}
      {ornament === 3 && (
        <g fill={c.rule}>
          {[0, 1, 2].map((k) => (
            <circle key={k} cx={52 + k * 12} cy={small ? 26 : 32} r={2.4} />
          ))}
        </g>
      )}
      <g style={{ fontFamily: "var(--font-serif)" }} fill={c.ink} textAnchor="middle">
        {lines.map((line, i) => (
          <text key={i} x={64} y={top + i * (fontSize + 3)} fontSize={fontSize} fontWeight={500}>
            {line}
          </text>
        ))}
      </g>
      <line x1={36} y1={small ? 146 : 140} x2={92} y2={small ? 146 : 140} stroke={c.rule} strokeWidth={1} opacity={0.8} />
      <text
        x={64}
        y={small ? 162 : 158}
        fontSize={small ? 8.5 : 8}
        letterSpacing={1}
        textAnchor="middle"
        fill={c.ink}
        style={{ fontFamily: "var(--font-sans)" }}
      >
        {wrap(author.toUpperCase(), 24, 1)[0]}
      </text>
    </svg>
  );
});
