import { useMemo } from "react";
import { hashWord, seeded } from "./logic";

/**
 * A small generated emblem for a future domain, seeded by the word, so "Quantum computing"
 * always draws the same figure: a horizon line, a rising sun or moon, orbits, and a few stars.
 * Drawn in maroon and ink on paper; decorative (the card's text names the domain).
 */
export function HorizonGlyph({ word, size = 120 }: { word: string; size?: number }) {
  const shapes = useMemo(() => {
    const rnd = seeded(hashWord(word));
    const horizon = 70 + rnd() * 14;
    const sunR = 14 + rnd() * 14;
    const sunX = 30 + rnd() * 60;
    const rings = 1 + Math.floor(rnd() * 3);
    const tilt = -30 + rnd() * 60;
    const stars = Array.from({ length: 4 + Math.floor(rnd() * 6) }, () => ({
      x: 8 + rnd() * 104,
      y: 8 + rnd() * (horizon - 24),
      r: 0.8 + rnd() * 1.6,
    }));
    const hills = Array.from({ length: 3 }, (_, i) => ({
      d: `M0 ${horizon + 6 + i * 9} Q ${30 + rnd() * 60} ${horizon - 4 + i * 8 - rnd() * 10} 120 ${horizon + 4 + i * 9} L120 120 L0 120 Z`,
      o: 0.08 + i * 0.07,
    }));
    const full = rnd() > 0.45;
    return { horizon, sunR, sunX, rings, tilt, stars, hills, full };
  }, [word]);
  const { horizon, sunR, sunX, rings, tilt, stars, hills, full } = shapes;
  const clipId = `hz-${hashWord(word).toString(36)}`;
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" className="block">
      <defs>
        <clipPath id={clipId}>
          <rect x="0" y="0" width="120" height={horizon} />
        </clipPath>
      </defs>
      <rect width="120" height="120" rx="14" fill="var(--color-canvas-soft)" />
      {stars.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="var(--color-ink)" opacity={0.35} />
      ))}
      <g clipPath={`url(#${clipId})`}>
        <circle cx={sunX} cy={horizon} r={sunR} fill="var(--color-primary)" opacity={full ? 0.9 : 0.18} />
        {!full && <circle cx={sunX} cy={horizon} r={sunR} fill="none" stroke="var(--color-primary)" strokeWidth="1.4" />}
        {Array.from({ length: rings }, (_, i) => (
          <ellipse
            key={i}
            cx={sunX}
            cy={horizon - sunR * 0.2}
            rx={sunR + 10 + i * 9}
            ry={(sunR + 10 + i * 9) * 0.32}
            fill="none"
            stroke="var(--color-ink)"
            strokeWidth="0.9"
            opacity={0.55 - i * 0.12}
            transform={`rotate(${tilt} ${sunX} ${horizon - sunR * 0.2})`}
          />
        ))}
      </g>
      {hills.map((h, i) => (
        <path key={i} d={h.d} fill="var(--color-ink)" opacity={h.o} />
      ))}
      <line x1="6" x2="114" y1={horizon} y2={horizon} stroke="var(--color-ink)" strokeWidth="1" opacity="0.6" />
    </svg>
  );
}
