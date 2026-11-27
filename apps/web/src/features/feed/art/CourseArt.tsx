import { memo, useMemo } from "react";
import { drawMotif, H, W } from "./motifs";
import { palette } from "./palette";
import { rng } from "./rng";

/**
 * A course spotlight's illustration: the motif drawn from the course's seed and palette, with
 * the course code set into the picture (the subject in outline capitals, the number on a rule).
 * Decorative: the card's heading names the course.
 */
export const CourseArt = memo(function CourseArt({
  code,
  motif,
  seed,
  paletteIndex,
  className,
}: {
  code: string;
  motif: string;
  seed: number;
  paletteIndex: number;
  className?: string;
}) {
  const p = palette(paletteIndex);
  const art = useMemo(() => drawMotif(motif, rng(seed), p), [motif, seed, p]);
  const [subject = code, number = ""] = code.split(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid slice"
      className={className}
      aria-hidden="true"
      focusable="false"
      style={{ background: p.ground }}
    >
      <rect width={W} height={H} fill={p.ground} />
      <text
        x={14}
        y={H - 16}
        fontSize={84}
        fontWeight={700}
        letterSpacing={6}
        fill="none"
        stroke={p.ink}
        strokeWidth={1.1}
        opacity={0.28}
        style={{ fontFamily: "var(--font-sans)" }}
      >
        {subject}
      </text>
      {art}
      <g style={{ fontFamily: "var(--font-sans)" }}>
        <rect x={W - 118} y={14} width={104} height={24} rx={12} fill={p.ground} opacity={0.88} />
        <text x={W - 66} y={30.5} fontSize={12} fontWeight={600} letterSpacing={1.6} textAnchor="middle" fill={p.ink}>
          {subject} {number}
        </text>
      </g>
    </svg>
  );
});
