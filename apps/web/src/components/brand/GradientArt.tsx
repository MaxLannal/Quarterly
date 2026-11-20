import { useId } from "react";
import { cn } from "@/lib/utils";

/**
 * The art panel of the redesign (docs/DESIGN.md "Maroon and night"): sweeping folds of crimson and
 * coral light over maroon and black, in the manner of the reference login card's right panel.
 * Generated SVG (no image is fetched); `seed` turns and shifts the folds so each page has its own.
 * The folds drift slowly; under reduced motion they stay put (the global rule stops animations).
 */
export function GradientArt({ seed = "quarterly", className }: { seed?: string; className?: string }) {
  const id = useId().replace(/:/g, "");
  const h = [...seed].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) >>> 0, 7);
  const flip = h % 2 === 0;
  const tilt = (h % 17) - 8; // degrees
  const shift = (h % 23) - 11; // percent of the width
  return (
    <div
      aria-hidden="true"
      className={cn("gradient-art pointer-events-none absolute inset-0 -z-20 overflow-hidden bg-night", className)}
    >
      <svg
        className="absolute inset-[-8%] size-[116%]"
        viewBox="0 0 600 800"
        preserveAspectRatio="xMidYMid slice"
        style={{ transform: `rotate(${tilt}deg) translateX(${shift}%) scaleX(${flip ? -1 : 1})` }}
      >
        <defs>
          <linearGradient id={`${id}-fold`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ff6f8d" />
            <stop offset="0.42" stopColor="#df2a52" />
            <stop offset="1" stopColor="#5c0a1d" />
          </linearGradient>
          <linearGradient id={`${id}-wave`} x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor="#3a0714" />
            <stop offset="0.55" stopColor="#d9264e" />
            <stop offset="1" stopColor="#ff9a76" />
          </linearGradient>
          <radialGradient id={`${id}-glow`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#ffb08a" stopOpacity="0.95" />
            <stop offset="0.5" stopColor="#ff7a6b" stopOpacity="0.45" />
            <stop offset="1" stopColor="#ff7a6b" stopOpacity="0" />
          </radialGradient>
          <filter id={`${id}-soft`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="22" />
          </filter>
          <filter id={`${id}-edge`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" />
          </filter>
        </defs>
        <rect width="600" height="800" fill="#13040a" />
        {/* the deep maroon field */}
        <ellipse cx="480" cy="200" rx="250" ry="300" fill="#3d0814" filter={`url(#${id}-soft)`} />
        {/* the great crimson fold sweeping down the left, with a pale rim */}
        <g className="gradient-art-drift-a">
          <path
            d="M -80 -60 C 170 -30 230 220 180 430 C 140 600 40 720 -80 780 Z"
            fill={`url(#${id}-fold)`}
            opacity="0.92"
            filter={`url(#${id}-edge)`}
          />
          <path
            d="M 240 -60 C 265 120 245 280 180 420"
            stroke="#ffd2c2"
            strokeOpacity="0.55"
            strokeWidth="5"
            fill="none"
            filter={`url(#${id}-edge)`}
          />
        </g>
        {/* the coral glow under the dark hill */}
        <ellipse className="gradient-art-drift-b" cx="450" cy="640" rx="170" ry="100" fill={`url(#${id}-glow)`} />
        {/* the wave of crimson light low on the right */}
        <path
          className="gradient-art-drift-b"
          d="M 660 470 C 540 450 490 540 430 590 C 350 660 260 730 230 880 L 660 880 Z"
          fill={`url(#${id}-wave)`}
          opacity="0.9"
          filter={`url(#${id}-edge)`}
        />
        {/* the dark hill */}
        <path
          d="M 60 900 C 190 650 300 540 400 540 C 490 540 530 610 660 620 L 660 900 Z"
          fill="#160409"
          opacity="0.92"
          filter={`url(#${id}-edge)`}
        />
        <ellipse cx="300" cy="860" rx="320" ry="120" fill="#d9264e" opacity="0.35" filter={`url(#${id}-soft)`} />
      </svg>
    </div>
  );
}
