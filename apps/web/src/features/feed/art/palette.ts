/**
 * The illustrations' palettes, all from the design tokens in index.css (maroon, ink, paper, the
 * maroon wash and a touch of the data colours). Six palettes; the API picks one per course.
 */
export interface Palette {
  /** The panel's ground. */
  ground: string;
  /** Lines and type. */
  ink: string;
  /** The one strong colour of the picture. */
  accent: string;
  /** A second, quieter colour. */
  second: string;
  /** Faint fills (washes, far layers). */
  soft: string;
  /** Whether the ground is dark (type and lines are light). */
  dark: boolean;
}

const v = (name: string) => `var(--color-${name})`;

export const PALETTES: readonly Palette[] = [
  { ground: v("canvas"), ink: v("ink"), accent: v("primary"), second: v("data-1"), soft: v("hairline"), dark: false },
  { ground: v("primary-wash"), ink: v("primary"), accent: v("ink"), second: v("data-2"), soft: v("on-inverse-soft"), dark: false },
  { ground: v("surface-dark"), ink: v("on-dark"), accent: v("orb-maroon"), second: v("data-2"), soft: v("surface-dark-elevated"), dark: true },
  { ground: v("canvas-soft"), ink: v("ink"), accent: v("data-3"), second: v("primary"), soft: v("hairline-soft"), dark: false },
  { ground: v("primary"), ink: v("on-primary"), accent: v("primary-wash"), second: v("data-2"), soft: v("primary-hover"), dark: true },
  { ground: v("surface-strong"), ink: v("ink"), accent: v("data-4"), second: v("data-5"), soft: v("hairline-strong"), dark: false },
];

export function palette(index: number): Palette {
  return PALETTES[((index % PALETTES.length) + PALETTES.length) % PALETTES.length] as Palette;
}
