/**
 * The reading room of Harper Memorial Library, as geometry: a long hall seen down its length in
 * one-point perspective, with tall pointed windows down both walls, a beamed ceiling, long tables
 * with reading lamps, rows of pendant lights, and shafts of sunlight that fall through the
 * south windows (the left wall) across the room to the floor. Everything is computed once, in
 * hall units (1 unit ~ 1 m), and projected into a 1600 x 1000 picture. Pure functions, no DOM:
 * HarperHall.tsx draws the result. The proportions are a drawing, not a survey.
 */

export const VW = 1600;
export const VH = 1000;
/** The vanishing point (eye level, a little below the middle so the ceiling shows). */
export const CX = 800;
export const CY = 470;
const F = 560; // focal length, px
const EYE = 5.4; // eye height
const HALF = 8; // half the hall's width (walls at x = -8 and x = 8)
const GLASS = 8.5; // the glass sits back in the wall
const CEIL = 14.5;
export const FAR = 58; // the far wall
const NEAR = 4;

export type Pt = [number, number];

export function project(x: number, y: number, z: number): Pt {
  return [CX + (F * x) / z, CY - (F * (y - EYE)) / z];
}

export function d(points: Pt[], close = true): string {
  return "M" + points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join("L") + (close ? "Z" : "");
}

/** Monotone-chain convex hull (for a shaft of light: the window and its patch on the floor). */
export function hull(points: Pt[]): Pt[] {
  const p = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o: Pt, a: Pt, b: Pt) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const build = (list: Pt[]) => {
    const out: Pt[] = [];
    for (const q of list) {
      while (out.length >= 2 && cross(out[out.length - 2] as Pt, out[out.length - 1] as Pt, q) <= 0) out.pop();
      out.push(q);
    }
    return out;
  };
  const lower = build(p);
  const upper = build([...p].reverse());
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

/** A small deterministic random sequence, so the picture is the same on every load. */
export function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const cubic = (a: number, b: number, c: number, e: number, t: number) =>
  (1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * c + t ** 3 * e;

/** A pointed (Gothic) window in wall coordinates (depth z, height y), sill first, anticlockwise. */
function arch(z1: number, z2: number, sill: number, spring: number, apex: number, n = 8): [number, number][] {
  const zc = (z1 + z2) / 2;
  const w = z2 - z1;
  const h = apex - spring;
  const out: [number, number][] = [
    [z1, sill],
    [z2, sill],
    [z2, spring],
  ];
  for (let i = 1; i <= n; i++) {
    const t = i / n;
    out.push([cubic(z2, z2, zc + 0.14 * w, zc, t), cubic(spring, spring + 0.6 * h, apex - 0.32 * h, apex, t)]);
  }
  for (let i = 1; i <= n; i++) {
    const t = i / n;
    out.push([cubic(zc, zc - 0.14 * w, z1, z1, t), cubic(apex, apex - 0.32 * h, spring + 0.6 * h, spring, t)]);
  }
  return out;
}

export interface Window {
  side: "left" | "right";
  depth: number;
  glass: string;
  /** The far jamb: the lit thickness of the wall beside the glass. */
  jamb: string;
  /** Mullions, transom and lead lines. */
  leads: string;
  /** The round tracery in the head. */
  rose: string;
  /** Its reflection in the polished floor (mirrored under the floor plane). */
  reflection: string;
}

export interface Shaft {
  id: string;
  d: string;
  pool: string;
  from: Pt;
  to: Pt;
  /** Which of three breathing groups (a cloud passing makes them dim one after another). */
  group: 0 | 1 | 2;
}

export interface Lamp {
  at: Pt;
  r: number;
  depth: number;
}

export interface Mote {
  at: Pt;
  r: number;
  delay: number;
  duration: number;
  drift: number;
}

export interface Hall {
  wallLeft: string;
  wallRight: string;
  ceiling: string;
  floor: string;
  farWall: string;
  farWindow: string;
  farReflection: string;
  farLeads: string;
  shelves: string;
  spines: { d: string; tone: number }[];
  beamsFront: string;
  beamsUnder: string;
  ribs: string;
  windows: Window[];
  shafts: Shaft[];
  tablesTop: string;
  tablesSide: string;
  tableLegs: string;
  lamps: Lamp[];
  pendants: Lamp[];
  cords: string;
  motes: Mote[];
  stars: Pt[];
  bloom: Pt;
}

const BAYS = [8, 14, 20, 26, 32, 38, 44, 50];
const WIN_W = 3.4;
const SILL = 4.6;
const SPRING = 10.6;
const APEX = 12.9;
/** Sunlight comes from the south, through the left windows, falling across the room. */
const SUN = { x: 0.62, y: -0.58, z: 0.2 };

function wallPoint(side: "left" | "right", x: number, y: number, z: number): Pt {
  return project(side === "left" ? -x : x, y, z);
}

function buildWindow(side: "left" | "right", c: number): Window {
  const z1 = c - WIN_W / 2;
  const z2 = c + WIN_W / 2;
  const outline = arch(z1, z2, SILL, SPRING, APEX);
  const glass = d(outline.map(([z, y]) => wallPoint(side, GLASS, y, z)));
  // The far jamb (it faces the viewer): between the wall face and the glass, at depth z2.
  const jambPts: Pt[] = [];
  const edge = outline.filter(([z]) => Math.abs(z - z2) < 1e-6 || z >= (z1 + z2) / 2);
  for (const [z, y] of edge) jambPts.push(wallPoint(side, GLASS, y, z));
  for (const [z, y] of [...edge].reverse()) jambPts.push(wallPoint(side, HALF, y, z + 0.02));
  const jamb = d(jambPts);
  // Two mullions, a transom, and lead lines every 0.55 units.
  const lines: string[] = [];
  const third = (z2 - z1) / 3;
  for (const z of [z1 + third, z1 + 2 * third]) lines.push(d([wallPoint(side, GLASS, SILL, z), wallPoint(side, GLASS, SPRING + 0.9, z)], false));
  const transom = SILL + (SPRING - SILL) * 0.6;
  lines.push(d([wallPoint(side, GLASS, transom, z1), wallPoint(side, GLASS, transom, z2)], false));
  for (let y = SILL + 0.55; y < SPRING; y += 0.55) {
    if (Math.abs(y - transom) < 0.2) continue;
    lines.push(d([wallPoint(side, GLASS, y, z1), wallPoint(side, GLASS, y, z2)], false));
  }
  const leads = lines.join(" ");
  const rosePts: Pt[] = [];
  const rc = (z1 + z2) / 2;
  const ry = SPRING + 1.05;
  for (let i = 0; i < 18; i++) {
    const a = (i / 18) * Math.PI * 2;
    rosePts.push(wallPoint(side, GLASS, ry + Math.sin(a) * 0.55, rc + Math.cos(a) * 0.55));
  }
  const reflection = d(outline.map(([z, y]) => wallPoint(side, GLASS, -y, z)));
  return { side, depth: c, glass, jamb, leads, rose: d(rosePts), reflection };
}

function buildShaft(c: number, i: number): Shaft {
  const z1 = c - WIN_W / 2 + 0.25;
  const z2 = c + WIN_W / 2 - 0.25;
  const outline = arch(z1, z2, SILL, SPRING, APEX, 4);
  const top: Pt[] = [];
  const floor: Pt[] = [];
  for (const [z, y] of outline) {
    const x0 = -GLASS;
    const t = y / -SUN.y;
    top.push(project(x0, y, z));
    floor.push(project(x0 + SUN.x * t, 0, z + SUN.z * t));
  }
  const cx = (pts: Pt[]) => [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length] as Pt;
  return {
    id: `shaft-${i}`,
    d: d(hull([...top, ...floor])),
    pool: d(hull(floor)),
    from: cx(top),
    to: cx(floor),
    group: (i % 3) as 0 | 1 | 2,
  };
}

export function buildHall(): Hall {
  const r = rng(1912);
  const corner = (x: number, y: number) => [project(x, y, NEAR), project(x, y, FAR)] as const;
  const [lfN, lfF] = corner(-HALF, 0);
  const [lcN, lcF] = corner(-HALF, CEIL);
  const [rfN, rfF] = corner(HALF, 0);
  const [rcN, rcF] = corner(HALF, CEIL);

  // Bookcases under the windows: shelf lines along both walls, and book spines in the near bays.
  const shelfLines: string[] = [];
  for (const side of ["left", "right"] as const)
    for (const y of [0.9, 1.75, 2.6, 3.45]) shelfLines.push(d([wallPoint(side, HALF, y, NEAR), wallPoint(side, HALF, y, FAR)], false));
  const spines: { d: string; tone: number }[] = [];
  for (const side of ["left", "right"] as const)
    for (const y of [0.9, 1.75, 2.6]) {
      let z = 4.4;
      while (z < 34) {
        const tall = 0.55 + r() * 0.25;
        spines.push({ d: d([wallPoint(side, HALF, y + 0.04, z), wallPoint(side, HALF, y + tall, z)], false), tone: Math.floor(r() * 4) });
        z += 0.07 + r() * 0.09 + z * 0.006;
      }
    }

  // The ceiling: a transverse beam at every bay line, and two long beams.
  const front: string[] = [];
  const under: string[] = [];
  for (let z = 5; z < FAR; z += 6) {
    front.push(d([project(-HALF, CEIL, z), project(HALF, CEIL, z), project(HALF, CEIL - 0.75, z), project(-HALF, CEIL - 0.75, z)]));
    under.push(d([project(-HALF, CEIL - 0.75, z), project(HALF, CEIL - 0.75, z), project(HALF, CEIL - 0.75, z + 0.6), project(-HALF, CEIL - 0.75, z + 0.6)]));
  }
  const ribs: string[] = [];
  for (const x of [-3.4, 3.4])
    ribs.push(d([project(x - 0.22, CEIL - 0.3, NEAR), project(x + 0.22, CEIL - 0.3, NEAR), project(x + 0.22, CEIL - 0.3, FAR), project(x - 0.22, CEIL - 0.3, FAR)]));

  const windows: Window[] = [];
  const shafts: Shaft[] = [];
  BAYS.forEach((c, i) => {
    windows.push(buildWindow("left", c), buildWindow("right", c));
    shafts.push(buildShaft(c, i));
  });

  // Long tables in two rows either side of the aisle, with two lamps each.
  const tops: string[] = [];
  const sides: string[] = [];
  const legs: string[] = [];
  const lamps: Lamp[] = [];
  for (let k = 0; k < 8; k++) {
    const z0 = 6 + k * 6.2;
    const z1 = z0 + 5;
    for (const [x0, x1, inner] of [
      [-5.1, -1.9, -1.9],
      [1.9, 5.1, 1.9],
    ] as const) {
      tops.push(d([project(x0, 2.45, z0), project(x1, 2.45, z0), project(x1, 2.45, z1), project(x0, 2.45, z1)]));
      sides.push(d([project(inner, 2.45, z0), project(inner, 2.45, z1), project(inner, 2.1, z1), project(inner, 2.1, z0)]));
      sides.push(d([project(x0, 2.45, z0), project(x1, 2.45, z0), project(x1, 2.1, z0), project(x0, 2.1, z0)]));
      for (const [x, z] of [
        [inner, z0 + 0.3],
        [inner, z1 - 0.3],
      ] as const)
        legs.push(d([project(x, 2.1, z), project(x, 0, z)], false));
      const lx = (x0 + x1) / 2;
      for (const z of [z0 + 1.3, z0 + 3.7]) {
        const at = project(lx, 2.95, z);
        lamps.push({ at, r: (F * 0.9) / z, depth: z });
      }
    }
  }

  // Pendant lights over the tables, on long cords.
  const pendants: Lamp[] = [];
  const cords: string[] = [];
  for (const x of [-3.4, 3.4])
    for (let z = 11; z < FAR - 3; z += 6) {
      pendants.push({ at: project(x, 10.6, z), r: (F * 1.6) / z, depth: z });
      cords.push(d([project(x, CEIL - 0.3, z), project(x, 10.85, z)], false));
    }

  // Dust in the sunlight: points inside the shafts.
  const motes: Mote[] = [];
  for (let i = 0; i < 90; i++) {
    const c = BAYS[Math.floor(r() * 5)] ?? BAYS[0] ?? 8;
    const z = c - WIN_W / 2 + 0.3 + r() * (WIN_W - 0.6);
    const y0 = SILL + r() * (SPRING - SILL);
    const t = (y0 / -SUN.y) * (0.15 + r() * 0.8);
    const x = -GLASS + SUN.x * t;
    const zz = z + SUN.z * t;
    const y = y0 + SUN.y * t;
    motes.push({ at: project(x, y, zz), r: Math.max(0.7, (F * 0.03) / zz), delay: -r() * 14, duration: 9 + r() * 9, drift: 6 + r() * 10 });
  }

  // The great window at the far end.
  const farArch = arch(-4.6, 4.6, 2.6, 9.6, 13.3, 10);
  const far = farArch.map(([x, y]) => project(x, y, FAR - 0.05));
  const farReflection = farArch.map(([x, y]) => project(x, -y, FAR - 0.05));
  const farLeads: string[] = [];
  for (const x of [-2.3, 0, 2.3]) farLeads.push(d([project(x, 2.6, FAR - 0.1), project(x, 10.4, FAR - 0.1)], false));
  for (let y = 3.6; y < 9.6; y += 1.2) farLeads.push(d([project(-4.6, y, FAR - 0.1), project(4.6, y, FAR - 0.1)], false));
  const stars: Pt[] = [];
  for (let i = 0; i < 14; i++) stars.push(project(-4 + r() * 8, 6 + r() * 6.5, FAR - 0.1));

  return {
    wallLeft: d([lfN, lfF, lcF, lcN]),
    wallRight: d([rfN, rfF, rcF, rcN]),
    ceiling: d([lcN, rcN, rcF, lcF]),
    floor: d([lfN, rfN, rfF, lfF]),
    farWall: d([lfF, rfF, rcF, lcF]),
    farWindow: d(far),
    farReflection: d(farReflection),
    farLeads: farLeads.join(" "),
    shelves: shelfLines.join(" "),
    spines,
    beamsFront: front.join(" "),
    beamsUnder: under.join(" "),
    ribs: ribs.join(" "),
    windows,
    shafts,
    tablesTop: tops.join(" "),
    tablesSide: sides.join(" "),
    tableLegs: legs.join(" "),
    lamps,
    pendants,
    cords: cords.join(" "),
    motes,
    stars,
    bloom: project(0, 8, FAR),
  };
}
