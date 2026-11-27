/**
 * The illustrations' palettes for the dark-glass world (docs/DESIGN.md "Dark glass"): deep
 * grounds of night, oxblood and garnet, lines of warm white or rose, and one strong colour of
 * light each (red, amber, ember, rose, a cold blue for contrast). Six palettes, varied enough
 * to tell neighbouring cards apart; the API picks one per course. Grounds are solid, because the
 * motifs fill shapes with the ground to hide what lies behind them.
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
  /** The light that falls across the picture from one corner (a glow over the art). */
  glow: string;
}

export const PALETTES: readonly Palette[] = [
  // Night: warm white lines, the red light.
  { ground: "#0d0608", ink: "#f3e6e8", accent: "#ff5c70", second: "#8fc8ea", soft: "#22161a", dark: true, glow: "#ff3d5a" },
  // Oxblood: rose lines on deep maroon, amber light.
  { ground: "#2a0811", ink: "#ffc9d1", accent: "#ffb547", second: "#ff5c70", soft: "#3f1220", dark: true, glow: "#ff6a3d" },
  // Smoke: grey glass, ember light.
  { ground: "#151012", ink: "#e9dfe1", accent: "#f08a4b", second: "#c79ab0", soft: "#261c1f", dark: true, glow: "#ff8a5c" },
  // Garnet: white on garnet, a cold blue for contrast.
  { ground: "#3b0a18", ink: "#fff1f3", accent: "#8fc8ea", second: "#ffb547", soft: "#561428", dark: true, glow: "#ff5c70" },
  // Ember: dark plum, rose light.
  { ground: "#1d0a14", ink: "#f7dfe8", accent: "#ff7d9a", second: "#b9c06e", soft: "#30142a", dark: true, glow: "#d9264e" },
  // Ash: near black with a lifted red.
  { ground: "#100b0c", ink: "#ddd2d4", accent: "#ff4d63", second: "#ffb547", soft: "#201719", dark: true, glow: "#ffffff" },
];

export function palette(index: number): Palette {
  return PALETTES[((index % PALETTES.length) + PALETTES.length) % PALETTES.length] as Palette;
}
