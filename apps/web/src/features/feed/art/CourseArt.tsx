import { memo, useId, useMemo } from "react";
import { drawMotif, H, W } from "./motifs";
import { palette } from "./palette";
import { rng } from "./rng";

/**
 * A course spotlight's illustration: the motif drawn from the course's seed and palette, with
 * the course code set into the picture (the subject in outline capitals, the number on a rule).
 * Over it, light falls from one corner (the palette's glow, screened) and the bottom sinks into
 * the dark, so the print reads as lit glass. Decorative: the card's heading names the course.
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
  const id = useId().replace(/:/g, "");
  // The light's corner follows the seed, so neighbouring cards differ.
  const cx = seed % 2 === 0 ? "18%" : "86%";
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid slice"
      className={className}
      aria-hidden="true"
      focusable="false"
      style={{ background: p.ground }}
    >
      <defs>
        <radialGradient id={`${id}-glow`} cx={cx} cy="8%" r="75%">
          <stop offset="0%" stopColor={p.glow} stopOpacity={0.42} />
          <stop offset="45%" stopColor={p.glow} stopOpacity={0.1} />
          <stop offset="100%" stopColor={p.glow} stopOpacity={0} />
        </radialGradient>
        <linearGradient id={`${id}-fall`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="55%" stopColor="#060203" stopOpacity={0} />
          <stop offset="100%" stopColor="#060203" stopOpacity={0.5} />
        </linearGradient>
      </defs>
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
        opacity={0.22}
        style={{ fontFamily: "var(--font-sans)" }}
      >
        {subject}
      </text>
      {art}
      <rect width={W} height={H} fill={`url(#${id}-glow)`} style={{ mixBlendMode: "screen" }} />
      <rect width={W} height={H} fill={`url(#${id}-fall)`} />
      <g style={{ fontFamily: "var(--font-mono)" }}>
        <rect x={W - 122} y={14} width={108} height={24} rx={12} fill={p.ground} opacity={0.72} stroke={p.ink} strokeOpacity={0.25} strokeWidth={0.8} />
        <text x={W - 68} y={30} fontSize={11} fontWeight={500} letterSpacing={1.8} textAnchor="middle" fill={p.ink}>
          {subject} {number}
        </text>
      </g>
    </svg>
  );
});
