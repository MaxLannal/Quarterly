import { useMemo } from "react";
import { buildHall, CX, CY, VH, VW } from "./harperGeometry";
import type { Scene } from "./NightScene";
import "./harper.css";

const SPINE_TONES = ["#3a1519", "#57202a", "#2a1012", "#6b2a2e"];

/**
 * Harper Memorial Library's reading room, drawn in light (the homepage hero, Max 2026-11-27):
 * the long hall in perspective, tall pointed windows down both walls, the beamed ceiling, long
 * tables with reading lamps and rows of pendant lights. By day, sun falls through the south
 * windows in shafts that cross the room to the floor, dust drifting in them; a passing cloud dims
 * the shafts one after another. By night the windows go to deep violet and the lamps take over.
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
            <stop offset="0" stopColor="#070304" />
            <stop offset="0.6" stopColor="#170a0c" />
            <stop offset="1" stopColor="#3a161b" />
          </linearGradient>
          <linearGradient id="hh-wall-r" x1={VW} y1="0" x2={CX} y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#060203" />
            <stop offset="0.6" stopColor="#150809" />
            <stop offset="1" stopColor="#36141a" />
          </linearGradient>
          <linearGradient id="hh-ceil" x1="0" y1="0" x2="0" y2={CY - 80} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#050203" />
            <stop offset="1" stopColor="#2c1015" />
          </linearGradient>
          <linearGradient id="hh-floor" x1="0" y1={VH} x2="0" y2={CY + 50} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#040102" />
            <stop offset="0.7" stopColor="#140708" />
            <stop offset="1" stopColor="#24100f" />
          </linearGradient>
          <linearGradient id="hh-glass-day" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#fffaf8" />
            <stop offset="0.3" stopColor="#ffe1e4" />
            <stop offset="0.72" stopColor="#ff8a9b" />
            <stop offset="1" stopColor="#b51d3b" />
          </linearGradient>
          <linearGradient id="hh-glass-day-shade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#f6eef8" />
            <stop offset="0.45" stopColor="#d9a7b6" />
            <stop offset="1" stopColor="#7a1d36" />
          </linearGradient>
          <linearGradient id="hh-glass-night" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#3a2a5c" />
            <stop offset="0.55" stopColor="#1f1433" />
            <stop offset="1" stopColor="#3d0f22" />
          </linearGradient>
          <radialGradient id="hh-bloom" cx={hall.bloom[0]} cy={hall.bloom[1]} r="400" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#fffaf8" stopOpacity="0.8" />
            <stop offset="0.14" stopColor="#ffd2d8" stopOpacity="0.28" />
            <stop offset="0.5" stopColor="#d9264e" stopOpacity="0.08" />
            <stop offset="1" stopColor="#d9264e" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hh-bloom-night" cx={hall.bloom[0]} cy={hall.bloom[1]} r="420" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#8f7cc8" stopOpacity="0.35" />
            <stop offset="0.4" stopColor="#5a2a6a" stopOpacity="0.12" />
            <stop offset="1" stopColor="#5a2a6a" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="hh-lamp">
            <stop offset="0" stopColor="#fff6ec" />
            <stop offset="0.18" stopColor="#ffd9c4" stopOpacity="0.85" />
            <stop offset="0.45" stopColor="#ff7a8c" stopOpacity="0.25" />
            <stop offset="1" stopColor="#ff5c70" stopOpacity="0" />
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
        <path d={hall.farWall} fill="#2e1116" />

        {/* The great window at the far end, and its bloom. */}
        <path d={hall.farWindow} className="hh-day" fill="url(#hh-glass-day)" />
        <path d={hall.farWindow} className="hh-night" fill="url(#hh-glass-night)" />
        <g className="hh-night">
          {hall.stars.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={i % 4 === 0 ? 1.4 : 0.8} fill="#fff4e8" opacity={0.75} />
          ))}
        </g>
        <path d={hall.farLeads} stroke="#14070a" strokeWidth="1.2" fill="none" opacity="0.8" />

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
        <path d={hall.beamsUnder} fill="#3b1a1f" opacity="0.9" />
        <path d={hall.beamsFront} fill="#0b0405" />
        <path d={hall.ribs} fill="#120607" />

        {/* Bookcases under the windows. */}
        <g opacity="0.85">
          {hall.spines.map((s, i) => (
            <path key={i} d={s.d} stroke={SPINE_TONES[s.tone]} strokeWidth="1.4" />
          ))}
        </g>
        <path d={hall.shelves} stroke="#4a2026" strokeWidth="1" fill="none" opacity="0.7" />

        {/* The windows: lit jamb, glass (day and night), leads and tracery. */}
        {hall.windows.map((w, i) => (
          <g key={i}>
            <path d={w.jamb} fill={w.side === "left" ? "#4a1d24" : "#2a0f14"} />
            <path d={w.glass} className="hh-day" fill={w.side === "left" ? "url(#hh-glass-day)" : "url(#hh-glass-day-shade)"} opacity={w.side === "left" ? 1 : 0.62} />
            <path d={w.glass} className="hh-night" fill="url(#hh-glass-night)" opacity={0.95} />
            <path d={w.leads} stroke="#12060a" strokeWidth={Math.max(0.6, 26 / w.depth)} fill="none" opacity="0.75" />
            <path d={w.rose} stroke="#12060a" strokeWidth={Math.max(0.6, 22 / w.depth)} fill="none" opacity="0.8" />
          </g>
        ))}

        {/* Tables. */}
        <path d={hall.tableLegs} stroke="#1a0b0d" strokeWidth="2" fill="none" />
        <path d={hall.tablesSide} fill="#0d0506" />
        <path d={hall.tablesTop} fill="#2a1114" stroke="#7a3a40" strokeOpacity="0.55" strokeWidth="1" />

        {/* Pendant cords. */}
        <path d={hall.cords} stroke="#26100f" strokeWidth="1" fill="none" opacity="0.8" />

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
                  <stop offset="0" stopColor="#fff6f4" stopOpacity="0.3" />
                  <stop offset="0.5" stopColor="#ffd0d6" stopOpacity="0.1" />
                  <stop offset="1" stopColor="#ff8a9b" stopOpacity="0.03" />
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
                  <path d={s.pool} fill="#ffe2e6" opacity="0.07" />
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
