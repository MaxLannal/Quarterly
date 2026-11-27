import { useMemo } from "react";
import { buildHall, CX, CY, VH, VW } from "./harperGeometry";
import type { Scene } from "./NightScene";
import "./harper.css";

const SPINE_TONES = ["#a8957f", "#8f7b68", "#bfae98", "#7d6c5d"];

/**
 * Harper Memorial Library's reading room, drawn in sunlit stone (the homepage, Max 2026-11-27):
 * the long hall in perspective, tall pointed windows down both walls, the beamed ceiling, long
 * tables with reading lamps and rows of pendant lights. By day, sun falls through the south
 * windows in shafts that cross the room to the floor, dust drifting in them; a passing cloud dims
 * the shafts one after another. By night the room goes to dusk blue and the lamps take over.
 * Three stacked SVG layers (the room, the light, the dust) so the moving parts never repaint the
 * room. Reduced motion: still light, no dust.
 */
export function HarperHall({ scene }: { scene: Scene }) {
  const hall = useMemo(buildHall, []);
  const night = scene === "night";
  const view = `0 0 ${VW} ${VH}`;
  return (
    <div className="harper" data-scene={scene}>
      {/* The room. */}
      <svg
        className="harper-layer"
        viewBox={view}
        preserveAspectRatio="xMidYMid slice"
        role="img"
        aria-label={`The reading room of Harper Memorial Library ${night ? "at night, lit by its lamps" : "in sunlight"}: tall pointed windows down both walls, long tables with reading lamps, and pendant lights under a beamed ceiling.`}
      >
        <defs>
          <linearGradient id="hh-wall-l" x1="0" y1="0" x2={CX} y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#d9d2c6" />
            <stop offset="0.6" stopColor="#e7e1d7" />
            <stop offset="1" stopColor="#f4f1eb" />
          </linearGradient>
          <linearGradient id="hh-wall-r" x1={VW} y1="0" x2={CX} y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#cfc7ba" />
            <stop offset="0.6" stopColor="#e1dbd0" />
            <stop offset="1" stopColor="#f1ede6" />
          </linearGradient>
          <linearGradient id="hh-ceil" x1="0" y1="0" x2="0" y2={CY - 80} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#bdb3a5" />
            <stop offset="1" stopColor="#e9e4dc" />
          </linearGradient>
          <linearGradient id="hh-floor" x1="0" y1={VH} x2="0" y2={CY + 50} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#c9bfb1" />
            <stop offset="0.7" stopColor="#ddd6cb" />
            <stop offset="1" stopColor="#ece8e1" />
          </linearGradient>
          <linearGradient id="hh-glass-day" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#ffffff" />
            <stop offset="0.55" stopColor="#f6f9fc" />
            <stop offset="1" stopColor="#dfe8f1" />
          </linearGradient>
          <linearGradient id="hh-glass-day-shade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#fbfcfd" />
            <stop offset="0.5" stopColor="#e9eef3" />
            <stop offset="1" stopColor="#ccd7e2" />
          </linearGradient>
          <linearGradient id="hh-glass-night" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#40507a" />
            <stop offset="0.55" stopColor="#2b3757" />
            <stop offset="1" stopColor="#3a3550" />
          </linearGradient>
          <radialGradient id="hh-bloom" cx={hall.bloom[0]} cy={hall.bloom[1]} r="400" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#ffffff" stopOpacity="0.9" />
            <stop offset="0.2" stopColor="#ffffff" stopOpacity="0.35" />
            <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hh-bloom-night" cx={hall.bloom[0]} cy={hall.bloom[1]} r="420" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#9fb0d8" stopOpacity="0.3" />
            <stop offset="1" stopColor="#9fb0d8" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hh-lamp">
            <stop offset="0" stopColor="#fff8e8" />
            <stop offset="0.2" stopColor="#ffe9bf" stopOpacity="0.8" />
            <stop offset="0.5" stopColor="#ffd28a" stopOpacity="0.22" />
            <stop offset="1" stopColor="#ffd28a" stopOpacity="0" />
          </radialGradient>
          <clipPath id="hh-floor-clip">
            <path d={hall.floor} />
          </clipPath>
          <filter id="hh-reflect" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="3.5" />
          </filter>
          <linearGradient id="hh-reflect-fade" x1="0" y1={CY + 40} x2="0" y2={VH} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#fff" stopOpacity="1" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
          <mask id="hh-reflect-mask">
            <rect x="0" y="0" width={VW} height={VH} fill="url(#hh-reflect-fade)" />
          </mask>
        </defs>

        <path d={hall.ceiling} fill="url(#hh-ceil)" />
        <path d={hall.floor} fill="url(#hh-floor)" />
        <path d={hall.wallLeft} fill="url(#hh-wall-l)" />
        <path d={hall.wallRight} fill="url(#hh-wall-r)" />
        <path d={hall.farWall} fill="#efeae2" />

        {/* The great window at the far end, and its bloom. */}
        <path d={hall.farWindow} className="hh-day" fill="url(#hh-glass-day)" />
        <path d={hall.farWindow} className="hh-night" fill="url(#hh-glass-night)" />
        <g className="hh-night">
          {hall.stars.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={i % 4 === 0 ? 1.4 : 0.8} fill="#fff4e8" opacity={0.75} />
          ))}
        </g>
        <path d={hall.farLeads} stroke="#8d847a" strokeWidth="1" fill="none" opacity="0.6" />

        {/* The windows and the great window, mirrored in the polished floor. */}
        <g clipPath="url(#hh-floor-clip)">
          <g mask="url(#hh-reflect-mask)" filter="url(#hh-reflect)">
            <g className="hh-day" opacity="0.2">
              <path d={hall.farReflection} fill="url(#hh-glass-day)" />
              {hall.windows.map((w, i) => (
                <path key={i} d={w.reflection} fill={w.side === "left" ? "url(#hh-glass-day)" : "url(#hh-glass-day-shade)"} />
              ))}
            </g>
            <g className="hh-night" opacity="0.28">
              <path d={hall.farReflection} fill="url(#hh-glass-night)" />
              {hall.windows.map((w, i) => (
                <path key={i} d={w.reflection} fill="url(#hh-glass-night)" />
              ))}
            </g>
          </g>
        </g>

        {/* Ceiling beams and the two long beams. */}
        <path d={hall.beamsUnder} fill="#9b9084" opacity="0.9" />
        <path d={hall.beamsFront} fill="#6f665c" />
        <path d={hall.ribs} fill="#7d7469" />

        {/* Bookcases under the windows. */}
        <g opacity="0.85">
          {hall.spines.map((s, i) => (
            <path key={i} d={s.d} stroke={SPINE_TONES[s.tone]} strokeWidth="1.4" />
          ))}
        </g>
        <path d={hall.shelves} stroke="#8d8276" strokeWidth="1" fill="none" opacity="0.7" />

        {/* Night: a dusk wash over the stone (the glass and the lamps are drawn over it). */}
        <rect className="hh-night" x="0" y="0" width={VW} height={VH} fill="#1f2638" opacity="0.62" />

        {/* The windows: lit jamb, glass (day and night), leads and tracery. */}
        {hall.windows.map((w, i) => (
          <g key={i}>
            <path d={w.jamb} fill={w.side === "left" ? "#e9e3da" : "#c9c0b3"} />
            <path d={w.glass} className="hh-day" fill={w.side === "left" ? "url(#hh-glass-day)" : "url(#hh-glass-day-shade)"} opacity={w.side === "left" ? 1 : 0.62} />
            <path d={w.glass} className="hh-night" fill="url(#hh-glass-night)" opacity={0.95} />
            <path d={w.leads} stroke="#8a8279" strokeWidth={Math.max(0.5, 20 / w.depth)} fill="none" opacity="0.55" />
            <path d={w.rose} stroke="#8a8279" strokeWidth={Math.max(0.5, 18 / w.depth)} fill="none" opacity="0.6" />
          </g>
        ))}

        {/* Tables. */}
        <path d={hall.tableLegs} stroke="#7a6f63" strokeWidth="2" fill="none" />
        <path d={hall.tablesSide} fill="#8f8376" />
        <path d={hall.tablesTop} fill="#b6aa9b" stroke="#d8cfc3" strokeOpacity="0.8" strokeWidth="1" />

        {/* Pendant cords. */}
        <path d={hall.cords} stroke="#6f665c" strokeWidth="1" fill="none" opacity="0.6" />

        <rect className="hh-day" x="0" y="0" width={VW} height={VH} fill="url(#hh-bloom)" style={{ mixBlendMode: "screen" }} />
        <rect className="hh-night" x="0" y="0" width={VW} height={VH} fill="url(#hh-bloom-night)" style={{ mixBlendMode: "screen" }} />
      </svg>

      {/* The light: sun shafts in three breathing groups, then the lamps. */}
      {[0, 1, 2].map((g) => (
        <svg key={g} className={`harper-layer harper-shafts harper-shafts-${g}`} viewBox={view} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <defs>
            {hall.shafts
              .filter((s) => s.group === g)
              .map((s) => (
                <linearGradient key={s.id} id={`hh-${s.id}`} x1={s.from[0]} y1={s.from[1]} x2={s.to[0]} y2={s.to[1]} gradientUnits="userSpaceOnUse">
                  <stop offset="0" stopColor="#ffffff" stopOpacity="0.55" />
                  <stop offset="0.5" stopColor="#ffffff" stopOpacity="0.22" />
                  <stop offset="1" stopColor="#ffffff" stopOpacity="0.06" />
                </linearGradient>
              ))}
            <filter id={`hh-blur-${g}`} x="-10%" y="-10%" width="120%" height="120%">
              <feGaussianBlur stdDeviation="7" />
            </filter>
          </defs>
          <g filter={`url(#hh-blur-${g})`}>
            {hall.shafts
              .filter((s) => s.group === g)
              .map((s) => (
                <g key={s.id}>
                  <path d={s.d} fill={`url(#hh-${s.id})`} />
                  <path d={s.pool} fill="#ffffff" opacity="0.35" />
                </g>
              ))}
          </g>
        </svg>
      ))}

      <svg className="harper-layer harper-lamps" viewBox={view} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        {hall.pendants.map((l, i) => (
          <g key={i}>
            <circle cx={l.at[0]} cy={l.at[1]} r={l.r * 3} fill="url(#hh-lamp)" opacity="0.4" />
            <ellipse cx={l.at[0]} cy={l.at[1]} rx={Math.max(1.4, l.r * 0.16)} ry={Math.max(1, l.r * 0.1)} fill="#fff4e6" />
          </g>
        ))}
        {hall.lamps.map((l, i) => (
          <circle key={i} cx={l.at[0]} cy={l.at[1]} r={l.r * 1.1} fill="url(#hh-lamp)" opacity="0.6" />
        ))}
      </svg>

      {/* Dust drifting in the sun. */}
      <svg className="harper-layer harper-dust" viewBox={view} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        {hall.motes.map((m, i) => (
          <circle
            key={i}
            className="harper-mote"
            cx={m.at[0]}
            cy={m.at[1]}
            r={m.r}
            style={{
              animationDelay: `${m.delay.toFixed(2)}s`,
              animationDuration: `${m.duration.toFixed(2)}s`,
              ["--drift" as string]: `${m.drift.toFixed(1)}px`,
            }}
          />
        ))}
      </svg>

      {/* Haze and the glass over the picture. */}
      <div className="harper-haze" aria-hidden="true" />
    </div>
  );
}
