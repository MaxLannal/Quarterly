/**
 * Generated illustrations for course spotlights: one family of layered geometry per motif (the
 * API names the motif from the course's subject family), drawn from a seed so a course always
 * gets the same picture. Pure SVG built here: no image is fetched from anywhere.
 */
import type { ReactNode } from "react";
import type { Palette } from "./palette";
import { between, pick, round, type Rand } from "./rng";

export const W = 400;
export const H = 250;

type Draw = (r: Rand, p: Palette) => ReactNode;
type Pt = [number, number];

/** A smooth closed path through points (Catmull-Rom as cubic Béziers). */
export function closed(points: Pt[]): string {
  const n = points.length;
  if (n < 3) return "";
  const at = (i: number) => points[((i % n) + n) % n] as Pt;
  let d = `M${round(at(0)[0])},${round(at(0)[1])}`;
  for (let i = 0; i < n; i++) {
    const [p0, p1, p2, p3] = [at(i - 1), at(i), at(i + 1), at(i + 2)];
    const c1: Pt = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2: Pt = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${round(c1[0])},${round(c1[1])} ${round(c2[0])},${round(c2[1])} ${round(p2[0])},${round(p2[1])}`;
  }
  return d + "Z";
}

/** A smooth open path through points. */
export function open(points: Pt[]): string {
  if (points.length < 2) return "";
  let d = `M${round(points[0]![0])},${round(points[0]![1])}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(i - 1, 0)] as Pt;
    const p1 = points[i] as Pt;
    const p2 = points[i + 1] as Pt;
    const p3 = points[Math.min(i + 2, points.length - 1)] as Pt;
    const c1: Pt = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2: Pt = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${round(c1[0])},${round(c1[1])} ${round(c2[0])},${round(c2[1])} ${round(p2[0])},${round(p2[1])}`;
  }
  return d;
}

function blob(r: Rand, cx: number, cy: number, radius: number, wobble = 0.14, n = 10): string {
  const pts: Pt[] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const k = radius * (1 + between(r, -wobble, wobble));
    pts.push([cx + Math.cos(a) * k, cy + Math.sin(a) * k]);
  }
  return closed(pts);
}

function stars(r: Rand, p: Palette, n: number): ReactNode[] {
  return Array.from({ length: n }, (_, i) => (
    <circle key={`s${i}`} cx={round(between(r, 0, W))} cy={round(between(r, 0, H))} r={round(between(r, 0.6, 1.6))} fill={p.ink} opacity={round(between(r, 0.2, 0.6))} />
  ));
}

// ------------------------------------------------------------------------------- the motifs

const lattice: Draw = (r, p) => {
  const a: Pt = [between(r, 34, 50), between(r, -9, 9)];
  const b: Pt = [between(r, -16, 16), between(r, 30, 42)];
  const o: Pt = [between(r, -30, 10), between(r, -20, 10)];
  const pts = new Map<string, Pt>();
  for (let i = -3; i < 14; i++)
    for (let j = -3; j < 10; j++) {
      const x = o[0] + i * a[0] + j * b[0];
      const y = o[1] + i * a[1] + j * b[1];
      if (x > -20 && x < W + 20 && y > -20 && y < H + 20) pts.set(`${i},${j}`, [x, y]);
    }
  const lines: ReactNode[] = [];
  const dots: ReactNode[] = [];
  let accentCell: Pt[] | null = null;
  for (const [key, [x, y]] of pts) {
    const [i, j] = key.split(",").map(Number) as [number, number];
    for (const [di, dj] of [[1, 0], [0, 1], [1, 1]] as const) {
      const q = pts.get(`${i + di},${j + dj}`);
      if (q && r() < (di && dj ? 0.18 : 0.6)) lines.push(<line key={`l${key}${di}${dj}`} x1={round(x)} y1={round(y)} x2={round(q[0])} y2={round(q[1])} stroke={p.ink} strokeWidth={0.8} opacity={0.3} />);
    }
    const big = r() < 0.07;
    dots.push(<circle key={`d${key}`} cx={round(x)} cy={round(y)} r={big ? 4.2 : 2} fill={big ? p.accent : p.ink} opacity={big ? 1 : 0.65} />);
    const right = pts.get(`${i + 1},${j}`);
    const down = pts.get(`${i},${j + 1}`);
    if (!accentCell && right && down && x > W * 0.45 && y > H * 0.25 && r() < 0.2) accentCell = [[x, y], right, down];
  }
  const cx = between(r, W * 0.25, W * 0.75);
  const cy = between(r, H * 0.3, H * 0.7);
  return [
    <circle key="halo" cx={round(cx)} cy={round(cy)} r={round(between(r, 70, 110))} fill="none" stroke={p.second} strokeWidth={1.4} strokeDasharray="2 6" opacity={0.8} />,
    ...lines,
    accentCell && <polygon key="cell" points={accentCell.map((q) => q.map(round).join(",")).join(" ")} fill={p.accent} opacity={0.85} />,
    ...dots,
  ];
};

const orbits: Draw = (r, p) => {
  const cx = between(r, W * 0.52, W * 0.78);
  const cy = between(r, H * 0.36, H * 0.6);
  const tilt = round(between(r, -32, 32));
  const out: ReactNode[] = stars(r, p, 46);
  for (let k = 1; k <= 5; k++) {
    const rx = 30 * k * between(r, 1, 1.12);
    const ry = rx * between(r, 0.32, 0.46);
    out.push(<ellipse key={`o${k}`} cx={round(cx)} cy={round(cy)} rx={round(rx)} ry={round(ry)} fill="none" stroke={p.ink} strokeWidth={k === 3 ? 1.4 : 0.9} strokeDasharray={k % 2 ? undefined : "3 5"} opacity={0.45} transform={`rotate(${tilt} ${round(cx)} ${round(cy)})`} />);
    const t = between(r, 0, Math.PI * 2);
    const ang = (tilt * Math.PI) / 180;
    const x = cx + rx * Math.cos(t) * Math.cos(ang) - ry * Math.sin(t) * Math.sin(ang);
    const y = cy + rx * Math.cos(t) * Math.sin(ang) + ry * Math.sin(t) * Math.cos(ang);
    out.push(<circle key={`p${k}`} cx={round(x)} cy={round(y)} r={round(between(r, 2.5, 6.5))} fill={k === 2 ? p.second : p.ink} />);
  }
  out.push(<circle key="halo" cx={round(cx)} cy={round(cy)} r={24} fill={p.accent} opacity={0.18} />);
  out.push(<circle key="sun" cx={round(cx)} cy={round(cy)} r={13} fill={p.accent} />);
  return out;
};

const circuit: Draw = (r, p) => {
  const out: ReactNode[] = [];
  const chip = { x: between(r, W * 0.48, W * 0.62), y: between(r, H * 0.22, H * 0.36), w: 118, h: 76 };
  const accentRow = Math.floor(between(r, 1, 8));
  for (let i = 0; i < 10; i++) {
    let x = -10;
    let y = 14 + i * 23;
    const pts: Pt[] = [[x, y]];
    while (x < W + 10) {
      x += between(r, 30, 90);
      pts.push([x, y]);
      if (r() < 0.55) {
        const dy = pick(r, [-23, 23]);
        x += 23;
        y = Math.min(Math.max(y + dy, 10), H - 10);
        pts.push([x, y]);
      }
    }
    const d = "M" + pts.map((q) => q.map(round).join(",")).join(" L");
    const hot = i === accentRow;
    out.push(<path key={`t${i}`} d={d} fill="none" stroke={hot ? p.accent : p.ink} strokeWidth={hot ? 2.6 : 1} opacity={hot ? 1 : 0.4} strokeLinejoin="round" />);
    const end = pts[Math.floor(between(r, 1, pts.length - 1))] as Pt;
    out.push(<circle key={`v${i}`} cx={round(end[0])} cy={round(end[1])} r={3.6} fill={p.ground} stroke={hot ? p.accent : p.ink} strokeWidth={1.4} />);
  }
  out.push(<rect key="chip" x={round(chip.x)} y={round(chip.y)} width={chip.w} height={chip.h} rx={6} fill={p.ground} stroke={p.ink} strokeWidth={1.6} />);
  for (let k = 0; k < 9; k++) {
    const px = chip.x + 10 + k * 12.5;
    out.push(<line key={`pt${k}`} x1={round(px)} y1={round(chip.y)} x2={round(px)} y2={round(chip.y - 9)} stroke={p.ink} strokeWidth={1.6} />);
    out.push(<line key={`pb${k}`} x1={round(px)} y1={round(chip.y + chip.h)} x2={round(px)} y2={round(chip.y + chip.h + 9)} stroke={p.ink} strokeWidth={1.6} />);
  }
  out.push(<rect key="die" x={round(chip.x + 34)} y={round(chip.y + 20)} width={50} height={36} rx={3} fill={p.second} opacity={0.9} />);
  return out;
};

const cells: Draw = (r, p) => {
  const out: ReactNode[] = [];
  const n = Math.floor(between(r, 5, 8));
  for (let i = 0; i < n; i++) {
    const R = between(r, 22, 56);
    const cx = between(r, 20, W - 20);
    const cy = between(r, 20, H - 20);
    out.push(<path key={`c${i}`} d={blob(r, cx, cy, R)} fill={p.soft} opacity={0.75} stroke={p.ink} strokeWidth={1.3} />);
    out.push(<path key={`m${i}`} d={blob(r, cx, cy, R * 0.86, 0.1)} fill="none" stroke={p.ink} strokeWidth={0.6} opacity={0.4} />);
    out.push(<circle key={`n${i}`} cx={round(cx + between(r, -R * 0.2, R * 0.2))} cy={round(cy + between(r, -R * 0.2, R * 0.2))} r={round(R * 0.3)} fill={i === 0 ? p.accent : p.second} opacity={i === 0 ? 1 : 0.55} />);
    for (let k = 0; k < 5; k++) {
      const a = between(r, 0, Math.PI * 2);
      const d = between(r, R * 0.45, R * 0.75);
      out.push(<circle key={`g${i}${k}`} cx={round(cx + Math.cos(a) * d)} cy={round(cy + Math.sin(a) * d)} r={round(between(r, 1.2, 2.8))} fill={p.ink} opacity={0.55} />);
    }
  }
  return out;
};

const waves: Draw = (r, p) => {
  const out: ReactNode[] = [];
  const hot = Math.floor(between(r, 1, 6));
  for (let i = 0; i < 8; i++) {
    const y0 = 24 + i * 29;
    const amp = between(r, 4, 17);
    const freq = between(r, 1.2, 4.2);
    const phase = between(r, 0, Math.PI * 2);
    const decay = between(r, 0, 1);
    const pts: Pt[] = [];
    for (let s = 0; s <= 48; s++) {
      const x = (s / 48) * W;
      const env = 1 - decay * Math.abs(s / 48 - 0.5);
      pts.push([x, y0 + Math.sin((s / 48) * Math.PI * 2 * freq + phase) * amp * env]);
    }
    const color = i === hot ? p.accent : i === hot + 2 ? p.second : p.ink;
    out.push(<path key={`w${i}`} d={open(pts)} fill="none" stroke={color} strokeWidth={i === hot ? 2.6 : 1.1} opacity={i === hot ? 1 : 0.5} />);
  }
  for (let k = 0; k < 40; k++) {
    const x = 10 + k * 10;
    out.push(<line key={`k${k}`} x1={x} y1={H - 8} x2={x} y2={H - 8 - (k % 5 === 0 ? 10 : 4)} stroke={p.ink} strokeWidth={0.8} opacity={0.5} />);
  }
  return out;
};

const curves: Draw = (r, p) => {
  const left = 40;
  const bottom = H - 34;
  const span = W - 80;
  const e1 = between(r, 0.55, 0.85);
  const e2 = between(r, 1.4, 2.1);
  const demand = (x: number) => 30 + (bottom - 50) * Math.pow((x - left) / span, e1);
  const supply = (x: number) => bottom - 16 - (bottom - 46) * Math.pow((x - left) / span, e2);
  const xs = Array.from({ length: 41 }, (_, i) => left + (i / 40) * span);
  let cross: Pt = [left + span / 2, demand(left + span / 2)];
  let best = Infinity;
  for (const x of xs) {
    const gap = Math.abs(demand(x) - supply(x));
    if (gap < best) {
      best = gap;
      cross = [x, (demand(x) + supply(x)) / 2];
    }
  }
  const out: ReactNode[] = [];
  for (let i = 0; i < 9; i++) {
    const h = between(r, 20, 120);
    out.push(<rect key={`b${i}`} x={left + 14 + i * 36} y={round(bottom - h)} width={20} height={round(h)} fill={p.soft} opacity={0.9} />);
  }
  out.push(<path key="ax" d={`M${left},18 V${bottom} H${W - 22}`} fill="none" stroke={p.ink} strokeWidth={1.4} />);
  out.push(<path key="d" d={open(xs.map((x) => [x, demand(x)] as Pt))} fill="none" stroke={p.ink} strokeWidth={2} />);
  out.push(<path key="s" d={open(xs.map((x) => [x, supply(x)] as Pt))} fill="none" stroke={p.second} strokeWidth={2} />);
  out.push(<path key="g" d={`M${round(cross[0])},${round(cross[1])} V${bottom} M${round(cross[0])},${round(cross[1])} H${left}`} stroke={p.ink} strokeWidth={1} strokeDasharray="3 4" opacity={0.7} />);
  out.push(<circle key="eq" cx={round(cross[0])} cy={round(cross[1])} r={6} fill={p.accent} />);
  return out;
};

const network: Draw = (r, p) => {
  const nodes: Pt[] = Array.from({ length: 24 }, () => [between(r, 16, W - 16), between(r, 14, H - 14)]);
  const dist = (a: Pt, b: Pt) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const out: ReactNode[] = [];
  nodes.forEach((a, i) => {
    const near = nodes.map((b, j) => [dist(a, b), j] as const).filter(([, j]) => j !== i).sort((x, y) => x[0] - y[0]).slice(0, 2);
    for (const [, j] of near) out.push(<line key={`e${i}-${j}`} x1={round(a[0])} y1={round(a[1])} x2={round(nodes[j]![0])} y2={round(nodes[j]![1])} stroke={p.ink} strokeWidth={0.9} opacity={0.35} />);
  });
  const centre: Pt = [W / 2, H / 2];
  const hubIndex = nodes.map((n, i) => [dist(n, centre), i] as const).sort((x, y) => x[0] - y[0])[0]![1];
  const hub = nodes[hubIndex] as Pt;
  nodes.forEach((n, i) => {
    if (i !== hubIndex && r() < 0.28) out.push(<line key={`h${i}`} x1={round(hub[0])} y1={round(hub[1])} x2={round(n[0])} y2={round(n[1])} stroke={p.accent} strokeWidth={1.4} opacity={0.75} />);
  });
  nodes.forEach((n, i) => {
    out.push(<circle key={`n${i}`} cx={round(n[0])} cy={round(n[1])} r={i === hubIndex ? 9 : round(between(r, 2.4, 5.5))} fill={i === hubIndex ? p.accent : r() < 0.2 ? p.second : p.ink} />);
  });
  out.push(<circle key="ring" cx={round(hub[0])} cy={round(hub[1])} r={17} fill="none" stroke={p.accent} strokeWidth={1} opacity={0.6} />);
  return out;
};

const columns: Draw = (r, p) => {
  const ground = H - 26;
  const n = Math.floor(between(r, 5, 8));
  const gap = (W - 60) / n;
  const top = between(r, 82, 104);
  const out: ReactNode[] = [];
  out.push(<circle key="sun" cx={round(between(r, 60, W - 60))} cy={round(between(r, 30, 60))} r={round(between(r, 22, 34))} fill={p.accent} opacity={0.9} />);
  if (r() < 0.6) out.push(<polygon key="ped" points={`22,${round(top - 16)} ${W / 2},${round(top - 62)} ${W - 22},${round(top - 16)}`} fill={p.soft} stroke={p.ink} strokeWidth={1.4} />);
  out.push(<rect key="ent" x={20} y={round(top - 16)} width={W - 40} height={14} fill={p.ground} stroke={p.ink} strokeWidth={1.4} />);
  for (let i = 0; i < n; i++) {
    const cw = between(r, 20, 26);
    const x = 30 + i * gap + (gap - cw) / 2;
    out.push(<rect key={`cap${i}`} x={round(x - 5)} y={round(top - 2)} width={round(cw + 10)} height={8} fill={p.ground} stroke={p.ink} strokeWidth={1.2} />);
    out.push(<rect key={`sh${i}`} x={round(x)} y={round(top + 6)} width={round(cw)} height={round(ground - top - 14)} fill={p.ground} stroke={p.ink} strokeWidth={1.2} />);
    for (let f = 1; f < 4; f++) out.push(<line key={`f${i}${f}`} x1={round(x + (cw * f) / 4)} y1={round(top + 9)} x2={round(x + (cw * f) / 4)} y2={round(ground - 11)} stroke={p.ink} strokeWidth={0.6} opacity={0.6} />);
    out.push(<rect key={`base${i}`} x={round(x - 4)} y={round(ground - 8)} width={round(cw + 8)} height={8} fill={i % 3 === 1 ? p.second : p.ground} stroke={p.ink} strokeWidth={1.2} />);
  }
  out.push(<rect key="stylo" x={10} y={ground} width={W - 20} height={10} fill={p.soft} stroke={p.ink} strokeWidth={1.2} />);
  return out;
};

const scrolls: Draw = (r, p) => {
  const out: ReactNode[] = [];
  const n = Math.floor(between(r, 2, 4));
  for (let i = 0; i < n; i++) {
    const w = between(r, 150, 230);
    const h = between(r, 70, 100);
    const x = between(r, 10, W - w - 10);
    const y = 20 + i * between(r, 55, 70);
    const rot = round(between(r, -7, 7));
    const lines: ReactNode[] = [];
    for (let k = 0; k < Math.floor(h / 13) - 1; k++) {
      const len = between(r, w * 0.4, w * 0.78);
      lines.push(<line key={`t${k}`} x1={round(x + 22)} y1={round(y + 16 + k * 12)} x2={round(x + 22 + len)} y2={round(y + 16 + k * 12)} stroke={p.ink} strokeWidth={1.6} opacity={0.45} strokeLinecap="round" />);
    }
    out.push(
      <g key={`s${i}`} transform={`rotate(${rot} ${round(x + w / 2)} ${round(y + h / 2)})`}>
        <rect x={round(x + 8)} y={round(y)} width={round(w - 16)} height={round(h)} fill={p.soft} stroke={p.ink} strokeWidth={1.2} />
        <rect x={round(x)} y={round(y - 6)} width={14} height={round(h + 12)} rx={7} fill={i === 0 ? p.second : p.ground} stroke={p.ink} strokeWidth={1.2} />
        <rect x={round(x + w - 14)} y={round(y - 6)} width={14} height={round(h + 12)} rx={7} fill={p.ground} stroke={p.ink} strokeWidth={1.2} />
        {lines}
      </g>,
    );
  }
  const sx = between(r, W * 0.6, W - 40);
  const sy = between(r, H * 0.55, H - 40);
  out.push(<circle key="seal" cx={round(sx)} cy={round(sy)} r={20} fill={p.accent} />);
  out.push(<circle key="seal2" cx={round(sx)} cy={round(sy)} r={13} fill="none" stroke={p.ground} strokeWidth={1.4} />);
  return out;
};

const pages: Draw = (r, p) => {
  const cx = W / 2 + between(r, -30, 30);
  const top = between(r, 34, 50);
  const bottom = H - between(r, 28, 40);
  const half = between(r, 140, 165);
  const sag = between(r, 10, 18);
  const left = `M${round(cx)},${round(top + 10)} Q${round(cx - half / 2)},${round(top - sag)} ${round(cx - half)},${round(top + 4)} L${round(cx - half)},${round(bottom)} Q${round(cx - half / 2)},${round(bottom - sag)} ${round(cx)},${round(bottom + 6)} Z`;
  const right = `M${round(cx)},${round(top + 10)} Q${round(cx + half / 2)},${round(top - sag)} ${round(cx + half)},${round(top + 4)} L${round(cx + half)},${round(bottom)} Q${round(cx + half / 2)},${round(bottom - sag)} ${round(cx)},${round(bottom + 6)} Z`;
  const out: ReactNode[] = [];
  for (let k = 1; k <= 3; k++) out.push(<path key={`e${k}`} d={`M${round(cx - half + k * 3)},${round(bottom + k * 4)} Q${round(cx - half / 2)},${round(bottom - sag + k * 4)} ${round(cx)},${round(bottom + 6 + k * 4)} Q${round(cx + half / 2)},${round(bottom - sag + k * 4)} ${round(cx + half - k * 3)},${round(bottom + k * 4)}`} fill="none" stroke={p.ink} strokeWidth={0.7} opacity={0.5} />);
  out.push(<path key="l" d={left} fill={p.ground} stroke={p.ink} strokeWidth={1.4} />);
  out.push(<path key="r" d={right} fill={p.ground} stroke={p.ink} strokeWidth={1.4} />);
  for (const side of [-1, 1]) {
    const rows = Math.floor((bottom - top - 30) / 11);
    for (let k = 0; k < rows; k++) {
      const y = top + 24 + k * 11;
      const from = cx + side * 14;
      const to = cx + side * (half - 16) * between(r, 0.7, 1);
      if (k === Math.floor(rows / 2) && side === 1) continue; // a paragraph break
      out.push(<path key={`t${side}${k}`} d={`M${round(from)},${round(y)} Q${round((from + to) / 2)},${round(y - sag / 3)} ${round(to)},${round(y)}`} fill="none" stroke={p.ink} strokeWidth={1.3} opacity={0.4} strokeLinecap="round" />);
    }
  }
  const rx = cx + between(r, 30, half - 40);
  out.push(<path key="rib" d={`M${round(rx)},${round(top - 2)} V${round(bottom + 34)} l-7,-8 l-7,8 V${round(top - 2)} Z`} fill={p.accent} />);
  return out;
};

/** A few stroke shapes for an abstract alphabet. */
function glyph(r: Rand, x: number, y: number, s: number, color: string, key: string): ReactNode {
  const parts: ReactNode[] = [];
  const count = Math.floor(between(r, 1, 4));
  for (let k = 0; k < count; k++) {
    const kind = pick(r, ["arc", "line", "dot", "hook", "bar"] as const);
    const x1 = x + between(r, 0.2, 0.8) * s;
    const y1 = y + between(r, 0.2, 0.8) * s;
    if (kind === "arc") parts.push(<path key={k} d={`M${round(x + s * 0.2)},${round(y1)} A${round(s * 0.3)},${round(s * 0.3)} 0 0 1 ${round(x + s * 0.8)},${round(y1)}`} />);
    else if (kind === "line") parts.push(<line key={k} x1={round(x1)} y1={round(y + s * 0.15)} x2={round(x + s - (x1 - x))} y2={round(y + s * 0.85)} />);
    else if (kind === "dot") parts.push(<circle key={k} cx={round(x1)} cy={round(y1)} r={2} fill={color} stroke="none" />);
    else if (kind === "hook") parts.push(<path key={k} d={`M${round(x1)},${round(y + s * 0.15)} V${round(y + s * 0.7)} q0,${round(s * 0.18)} ${round(-s * 0.2)},${round(s * 0.15)}`} />);
    else parts.push(<line key={k} x1={round(x + s * 0.15)} y1={round(y1)} x2={round(x + s * 0.85)} y2={round(y1)} />);
  }
  return (
    <g key={key} stroke={color} strokeWidth={2.2} fill="none" strokeLinecap="round">
      {parts}
    </g>
  );
}

const glyphs: Draw = (r, p) => {
  const out: ReactNode[] = [];
  const size = 44;
  const cols = Math.floor(W / size);
  const rows = Math.floor(H / size);
  const hot = [Math.floor(between(r, 1, cols - 1)), Math.floor(between(r, 0, rows - 1))];
  for (let i = 0; i < cols; i++)
    for (let j = 0; j < rows; j++) {
      const x = 8 + i * size;
      const y = 6 + j * size;
      const isHot = i === hot[0] && j === hot[1];
      out.push(<rect key={`c${i}-${j}`} x={x} y={y} width={size - 6} height={size - 6} rx={4} fill={isHot ? p.accent : j % 2 === i % 2 ? p.soft : "none"} opacity={isHot ? 1 : 0.6} />);
      out.push(glyph(r, x + 3, y + 3, size - 12, isHot ? p.ground : r() < 0.12 ? p.second : p.ink, `g${i}-${j}`));
    }
  return out;
};

const notes: Draw = (r, p) => {
  const out: ReactNode[] = [];
  const staves = [between(r, 46, 64), between(r, 150, 170)];
  const hot = Math.floor(between(r, 2, 10));
  staves.forEach((top, s) => {
    for (let k = 0; k < 5; k++) out.push(<line key={`l${s}${k}`} x1={10} y1={round(top + k * 9)} x2={W - 10} y2={round(top + k * 9)} stroke={p.ink} strokeWidth={0.9} opacity={0.55} />);
    out.push(<path key={`clef${s}`} d={`M34,${round(top + 44)} C20,${round(top + 30)} 46,${round(top + 6)} 36,${round(top - 8)} C28,${round(top - 18)} 22,${round(top + 10)} 34,${round(top + 22)} C44,${round(top + 32)} 26,${round(top + 40)} 26,${round(top + 30)}`} fill="none" stroke={p.ink} strokeWidth={2} />);
    let x = 70;
    let i = 0;
    while (x < W - 24) {
      const step = Math.floor(between(r, -2, 9));
      const y = top + 36 - step * 4.5;
      const up = step < 4;
      const color = s * 10 + i === hot ? p.accent : p.ink;
      out.push(<ellipse key={`n${s}${i}`} cx={round(x)} cy={round(y)} rx={5.6} ry={4} fill={color} transform={`rotate(-20 ${round(x)} ${round(y)})`} />);
      out.push(<line key={`st${s}${i}`} x1={round(up ? x + 5 : x - 5)} y1={round(y)} x2={round(up ? x + 5 : x - 5)} y2={round(up ? y - 28 : y + 28)} stroke={color} strokeWidth={1.4} />);
      if (i % 3 === 1 && up) out.push(<line key={`bm${s}${i}`} x1={round(x + 5)} y1={round(y - 28)} x2={round(x + 31)} y2={round(y - 30)} stroke={p.ink} strokeWidth={3.2} />);
      x += between(r, 22, 34);
      i++;
    }
  });
  out.push(<circle key="halo" cx={round(between(r, 80, W - 60))} cy={round(between(r, 100, 140))} r={34} fill={p.second} opacity={0.22} />);
  return out;
};

const frames: Draw = (r, p) => {
  const rot = round(between(r, -9, 9));
  const out: ReactNode[] = [];
  const y = 62;
  const h = 118;
  const frameCells: ReactNode[] = [];
  for (let k = 0; k < 4; k++) {
    const fx = 6 + k * 102;
    frameCells.push(<rect key={`fr${k}`} x={fx} y={y + 20} width={90} height={h - 40} rx={3} fill={k === 1 ? p.accent : k === 3 ? p.second : p.soft} opacity={k === 1 ? 0.95 : 0.7} />);
  }
  const holes: ReactNode[] = [];
  for (let k = 0; k < 26; k++) {
    holes.push(<rect key={`ht${k}`} x={4 + k * 16} y={y + 5} width={8} height={8} rx={1.5} fill={p.ground} />);
    holes.push(<rect key={`hb${k}`} x={4 + k * 16} y={y + h - 13} width={8} height={8} rx={1.5} fill={p.ground} />);
  }
  out.push(
    <g key="strip" transform={`rotate(${rot} ${W / 2} ${H / 2})`}>
      <rect x={-20} y={y} width={W + 40} height={h} fill={p.ink} opacity={0.9} />
      {frameCells}
      {holes}
    </g>,
  );
  const lx = between(r, W * 0.6, W - 50);
  const ly = between(r, 50, H - 50);
  out.push(<polygon key="beam" points={`${round(lx)},${round(ly)} 0,${round(ly - 90)} 0,${round(ly + 90)}`} fill={p.second} opacity={0.18} />);
  out.push(<circle key="lens" cx={round(lx)} cy={round(ly)} r={36} fill={p.ground} stroke={p.ink} strokeWidth={2} />);
  out.push(<circle key="lens2" cx={round(lx)} cy={round(ly)} r={22} fill="none" stroke={p.accent} strokeWidth={3} />);
  out.push(<circle key="lens3" cx={round(lx - 8)} cy={round(ly - 8)} r={5} fill={p.ink} opacity={0.6} />);
  return out;
};

const tiles: Draw = (r, p) => {
  const out: ReactNode[] = [];
  const s = between(r, 46, 58);
  const hot = Math.floor(between(r, 3, 20));
  let i = 0;
  for (let y = -s / 2; y < H + s; y += s)
    for (let x = -s / 2; x < W + s; x += s) {
      const c = s * 0.42;
      const square = (a: number) =>
        Array.from({ length: 4 }, (_, k) => {
          const t = a + (k * Math.PI) / 2;
          return `${round(x + Math.cos(t) * c)},${round(y + Math.sin(t) * c)}`;
        }).join(" ");
      const fill = i === hot ? p.accent : (Math.round(x / s) + Math.round(y / s)) % 2 ? p.soft : p.ground;
      out.push(<polygon key={`a${i}`} points={square(Math.PI / 4)} fill={fill} stroke={p.ink} strokeWidth={1} />);
      out.push(<polygon key={`b${i}`} points={square(0)} fill={fill} stroke={p.ink} strokeWidth={1} opacity={0.9} />);
      out.push(<circle key={`c${i}`} cx={round(x)} cy={round(y)} r={round(c * 0.36)} fill={i % 5 === 2 ? p.second : p.ground} stroke={p.ink} strokeWidth={0.8} />);
      i++;
    }
  return out;
};

const maps: Draw = (r, p) => {
  const out: ReactNode[] = [];
  for (let k = 0; k < 9; k++) out.push(<line key={`g${k}`} x1={k * 50} y1={0} x2={k * 50 - 30} y2={H} stroke={p.ink} strokeWidth={0.5} opacity={0.18} />);
  const peaks: Pt[] = [
    [between(r, 60, 170), between(r, 60, 150)],
    [between(r, 230, 350), between(r, 90, 190)],
  ];
  peaks.forEach((pk, i) => {
    const n = Math.floor(between(r, 5, 8));
    for (let k = n; k >= 1; k--) out.push(<path key={`c${i}${k}`} d={blob(r, pk[0], pk[1], k * between(r, 11, 15), 0.18, 12)} fill={k === 1 && i === 0 ? p.accent : "none"} stroke={p.ink} strokeWidth={k === n ? 1.2 : 0.8} opacity={k === 1 && i === 0 ? 0.9 : 0.5} />);
  });
  const river: Pt[] = Array.from({ length: 7 }, (_, k) => [(k / 6) * (W + 20) - 10, H * 0.55 + between(r, -60, 60)]);
  out.push(<path key="river" d={open(river)} fill="none" stroke={p.second} strokeWidth={3.2} strokeLinecap="round" />);
  const route: Pt[] = [peaks[0] as Pt, [between(r, 150, 250), between(r, 30, H - 30)], peaks[1] as Pt];
  out.push(<path key="route" d={open(route)} fill="none" stroke={p.accent} strokeWidth={1.8} strokeDasharray="5 5" />);
  const pin = peaks[1] as Pt;
  out.push(<path key="pin" d={`M${round(pin[0])},${round(pin[1])} c-9,-12 -9,-22 0,-24 c9,2 9,12 0,24 z`} fill={p.accent} />);
  out.push(<circle key="pinh" cx={round(pin[0])} cy={round(pin[1] - 16)} r={3} fill={p.ground} />);
  return out;
};

const arches: Draw = (r, p) => {
  const ground = H - 18;
  const n = Math.floor(between(r, 4, 7));
  const w = (W - 40) / n;
  const spring = between(r, 118, 150);
  const out: ReactNode[] = [];
  const rose: Pt = [between(r, 80, W - 80), between(r, 44, 70)];
  out.push(<circle key="rose" cx={round(rose[0])} cy={round(rose[1])} r={32} fill={p.soft} stroke={p.accent} strokeWidth={2.2} />);
  for (let k = 0; k < 12; k++) {
    const a = (k / 12) * Math.PI * 2;
    out.push(<line key={`sp${k}`} x1={round(rose[0])} y1={round(rose[1])} x2={round(rose[0] + Math.cos(a) * 32)} y2={round(rose[1] + Math.sin(a) * 32)} stroke={p.accent} strokeWidth={1} />);
  }
  out.push(<circle key="rose2" cx={round(rose[0])} cy={round(rose[1])} r={10} fill={p.accent} />);
  for (let i = 0; i < n; i++) {
    const x = 20 + i * w;
    const hgt = w * 0.9;
    const arch = (x0: number, ww: number, s0: number) =>
      `M${round(x0)},${ground} V${round(s0)} A${round(ww)},${round(ww)} 0 0 1 ${round(x0 + ww / 2)},${round(s0 - hgt * (ww / w))} A${round(ww)},${round(ww)} 0 0 1 ${round(x0 + ww)},${round(s0)} V${ground}`;
    out.push(<path key={`a${i}`} d={arch(x + 4, w - 8, spring)} fill={i % 3 === 1 ? p.second : p.ground} fillOpacity={i % 3 === 1 ? 0.35 : 1} stroke={p.ink} strokeWidth={1.5} />);
    out.push(<path key={`ai${i}`} d={arch(x + 14, w - 28, spring + 12)} fill="none" stroke={p.ink} strokeWidth={0.8} opacity={0.55} />);
    out.push(<line key={`m${i}`} x1={round(x + w / 2)} y1={round(spring + 8)} x2={round(x + w / 2)} y2={ground} stroke={p.ink} strokeWidth={0.8} opacity={0.55} />);
  }
  out.push(<line key="gr" x1={0} y1={ground} x2={W} y2={ground} stroke={p.ink} strokeWidth={1.6} />);
  return out;
};

const constellation: Draw = (r, p) => {
  const out: ReactNode[] = [];
  const corner: Pt = [between(r, -40, 40), H + 40];
  for (let k = 1; k <= 6; k++) out.push(<circle key={`ring${k}`} cx={round(corner[0])} cy={round(corner[1])} r={k * 60} fill="none" stroke={p.ink} strokeWidth={0.6} opacity={0.2} />);
  out.push(...stars(r, p, 60));
  const pts: Pt[] = Array.from({ length: 7 }, (_, k) => [40 + k * 50 + between(r, -14, 14), between(r, 30, H - 40)]);
  out.push(<path key="lines" d={"M" + pts.map((q) => q.map(round).join(",")).join(" L")} fill="none" stroke={p.ink} strokeWidth={1.1} opacity={0.65} />);
  if (r() < 0.7) out.push(<line key="branch" x1={round(pts[2]![0])} y1={round(pts[2]![1])} x2={round(pts[2]![0] + 30)} y2={round(pts[2]![1] + 50)} stroke={p.ink} strokeWidth={1.1} opacity={0.65} />);
  pts.forEach((q, k) => out.push(<circle key={`p${k}`} cx={round(q[0])} cy={round(q[1])} r={k === 3 ? 4.5 : round(between(r, 2, 3.4))} fill={k === 5 ? p.second : p.ink} />));
  const star = pts[3] as Pt;
  const s = 16;
  out.push(<path key="spark" d={`M${round(star[0])},${round(star[1] - s)} Q${round(star[0])},${round(star[1])} ${round(star[0] + s)},${round(star[1])} Q${round(star[0])},${round(star[1])} ${round(star[0])},${round(star[1] + s)} Q${round(star[0])},${round(star[1])} ${round(star[0] - s)},${round(star[1])} Q${round(star[0])},${round(star[1])} ${round(star[0])},${round(star[1] - s)}Z`} fill={p.accent} />);
  return out;
};

export const MOTIFS: Record<string, Draw> = {
  lattice,
  orbits,
  circuit,
  cells,
  waves,
  curves,
  network,
  columns,
  scrolls,
  pages,
  glyphs,
  notes,
  frames,
  tiles,
  maps,
  arches,
  constellation,
};

export function drawMotif(motif: string, r: Rand, p: Palette): ReactNode {
  return (MOTIFS[motif] ?? constellation)(r, p);
}
