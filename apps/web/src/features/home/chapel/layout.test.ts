import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { type ChapelData, decodeField, extendU, isChapelData, sampleField, sampleGrid, stoneRank } from "./field";
import { CHAPEL_SIDE_QUERY, hitTest, layoutGlyphs, type Metrics, placeChapel, seeded, SEPARATOR } from "./layout";
import { rgbAt, styleAt, weightFor } from "./palette";

// tests run from apps/web (npm run test)
const raw: unknown = JSON.parse(readFileSync(resolve(process.cwd(), "public/home/course-chapel.json"), "utf8"));
if (!isChapelData(raw)) throw new Error("course-chapel.json has an unexpected shape");
const data: ChapelData = raw;
const field = decodeField(data);
// every character half an em wide: enough to test the layout without a real font
const metrics: Metrics = { advance: () => 0.5 };

function layout(width: number, height: number, placement: "side" | "bottom", uiRight = 0) {
  return layoutGlyphs({ width, height, data, field, metrics, placement, uiRight, random: seeded(7) });
}

describe("the chapel drawing", () => {
  it("is sky above the chapel and building in the middle of it", () => {
    expect(sampleField(field, 0.9, 0.05).land).toBe(0);
    const middle = sampleField(field, (data.chapel.x0 + data.chapel.x1) / 2 - 0.05, 0.3);
    expect(middle.land).toBe(1);
    expect(middle.building).toBeGreaterThan(0.9);
  });

  it("extends sideways from its outer strips only, never repeating the chapel", () => {
    for (let u = -2; u <= 3; u += 0.01) {
      if (u >= 0 && u <= 1) continue;
      const e = extendU(field, u);
      expect(e < data.chapel.x0 || e > data.chapel.x1).toBe(true);
    }
  });

  const at = (u: number, v: number, skyT: number, ground: number) =>
    styleAt(
      sampleField(field, u, v),
      sampleGrid(field, field.height, u, v),
      sampleGrid(field, field.wide, u, v),
      u,
      v,
      data.masses,
      skyT,
      ground,
      (raw) => stoneRank(field, raw),
    );

  it("spreads the stone evenly over the reds", () => {
    expect(stoneRank(field, -1)).toBe(0);
    expect(stoneRank(field, 2)).toBe(1);
    const mid = stoneRank(field, field.stoneLevels[32]!);
    expect(mid).toBeGreaterThan(0.45);
    expect(mid).toBeLessThan(0.55);
  });

  it("draws the sky faint, grey and far, the chapel solid and red, and brings the lawn closer towards the bottom", () => {
    const sky = at(0.9, 0.05, 0.1, 0);
    expect(sky.alpha).toBeLessThan(0.2);
    expect(sky.depth).toBe(1);
    expect(sky.maroon).toBeLessThan(0.05);
    const stone = at(0.3, 0.3, 0.6, 0);
    expect(stone.alpha).toBeGreaterThan(0.9);
    expect(stone.maroon).toBe(1);
    const far = at(0.5, 0.85, 1, 0.1);
    const near = at(0.5, 0.98, 1, 0.9);
    expect(near.depth).toBeLessThan(far.depth);
  });

  it("puts the front nearest, the nave behind it and the tower furthest back", () => {
    const front = at(0.3, 0.3, 0.6, 0).depth;
    const nave = at(0.47, 0.5, 0.6, 0).depth;
    const tower = at(0.58, 0.3, 0.6, 0).depth;
    expect(front).toBeLessThan(nave);
    expect(nave).toBeLessThan(tower);
  });

  it("sets darker letters in heavier type", () => {
    expect(weightFor(0.2, 1, 1)).toBe(0);
    expect(weightFor(0.5, 1, 1)).toBe(1);
    expect(weightFor(0.8, 1, 1)).toBe(2);
    expect(weightFor(0.82, 0, 0.1)).toBe(2); // the sky
  });

  it("keeps to maroon, black and white", () => {
    // every colour on the maroon ramp is a red (or black/white), never another hue
    for (let t = 0; t <= 1; t += 0.05) {
      const [r, g, b] = rgbAt(t, 1);
      expect(r).toBeGreaterThanOrEqual(g);
      expect(r).toBeGreaterThanOrEqual(b - 0.01);
      const [nr, ng, nb] = rgbAt(t, 0);
      expect(Math.max(nr, ng, nb) - Math.min(nr, ng, nb)).toBeLessThan(0.05);
    }
    expect(rgbAt(0.36, 1).map((c) => Math.round(c * 255))).toEqual([128, 0, 0]);
    // evenly lighter at every step
    const light = (t: number) => rgbAt(t, 1).reduce((a, c) => a + c, 0);
    for (let t = 0.05; t <= 1; t += 0.05) expect(light(t)).toBeGreaterThan(light(t - 0.05));
  });
});

describe("placing the chapel", () => {
  it("fills the space right of the controls on a wide screen", () => {
    const f = placeChapel(1440, 835, data, field.aspect, "side", 470);
    const left = f.ox + data.chapel.x0 * f.w;
    const right = f.ox + data.chapel.x1 * f.w;
    const top = f.oy + data.chapel.y0 * f.h;
    const bottom = f.oy + data.chapel.y1 * f.h;
    expect(left).toBeGreaterThanOrEqual(440);
    expect(right).toBeLessThanOrEqual(1440);
    expect(bottom - top).toBeGreaterThan(835 * 0.75);
  });

  it("on a phone, lets the front with its spires fill the width", () => {
    const f = placeChapel(390, 780, data, field.aspect, "bottom");
    const facadeWidth = (data.facade.x1 - data.facade.x0) * f.w;
    expect(facadeWidth).toBeGreaterThan(390 * 0.7);
    expect(facadeWidth).toBeLessThanOrEqual(390);
    expect(f.oy + data.facade.y0 * f.h).toBeLessThan(780 * 0.1);
  });

  it("uses the same breakpoint as the page's CSS", () => {
    const css = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");
    expect(css).toContain(`@custom-variant chapel-side (@media ${CHAPEL_SIDE_QUERY});`);
  });
});

describe("laying out the titles", () => {
  const set = layout(1440, 835, "side", 470);

  it("covers the hero edge to edge with letters", () => {
    expect(set.count).toBeGreaterThan(10_000);
    expect(Math.min(...set.x)).toBeLessThan(0);
    expect(Math.max(...set.x)).toBeGreaterThan(1440);
    expect(set.rows[0]!.y).toBeLessThan(0);
    expect(set.rows[set.rows.length - 1]!.y).toBeGreaterThan(835);
  });

  it("spells real course titles, in order, with separators between them", () => {
    // walk each row and rebuild the titles from their letters
    const seen = new Map<number, string>();
    for (const row of set.rows) {
      for (let i = row.start; i < row.end; i++) {
        const w = set.word[i]!;
        if (w < 0) {
          expect(set.charset[set.glyph[i]!]).toBe(SEPARATOR.trim());
          continue;
        }
        seen.set(w, (seen.get(w) ?? "") + set.charset[set.glyph[i]!]);
      }
    }
    let whole = 0;
    for (const [w, letters] of seen) {
      const title = data.courses[w]![1].replace(/ /g, "");
      // titles cut by the hero's edges are a prefix or suffix of the real one
      expect(title.includes(letters)).toBe(true);
      if (letters === title) whole++;
    }
    expect(whole).toBeGreaterThan(300);
  });

  it("makes the lawn's rows larger towards the bottom", () => {
    const sizes = set.rows.map((r) => r.size);
    expect(sizes[sizes.length - 1]!).toBeGreaterThan(sizes[0]! * 1.5);
  });

  it("is the same layout for the same random seed", () => {
    const again = layout(1440, 835, "side", 470);
    expect(again.count).toBe(set.count);
    expect(Array.from(again.word.slice(0, 500))).toEqual(Array.from(set.word.slice(0, 500)));
  });
});

describe("finding the title under the pointer", () => {
  const set = layout(1440, 835, "side", 470);
  const row = set.rows[Math.floor(set.rows.length / 2)]!;
  const first = Array.from({ length: row.end - row.start }, (_, k) => row.start + k).find((i) => {
    const w = set.word[i]!;
    return w >= 0 && data.courses[w]![1].includes(" ") && set.x[i]! > 200;
  })!;
  const word = set.word[first]!;
  const letters = Array.from({ length: row.end - first }, (_, k) => first + k).filter((i) => set.word[i] === word);

  it("returns a letter of the title under the point", () => {
    const i = letters[0]!;
    const hit = hitTest(set, set.x[i]! + set.adv[i]! / 2, set.y[i]! - set.size[i]! * 0.3);
    expect(set.word[hit]).toBe(word);
  });

  it("counts the spaces between a title's words as part of it", () => {
    // a gap between two letters of the same title that is wider than one letter is a space
    const k = letters.findIndex((i, n) => n > 0 && set.x[i]! - (set.x[letters[n - 1]!]! + set.adv[letters[n - 1]!]!) > 1);
    expect(k).toBeGreaterThan(0);
    const before = letters[k - 1]!;
    const gapX = set.x[before]! + set.adv[before]! + 1;
    expect(set.word[hitTest(set, gapX, set.y[before]! - set.size[before]! * 0.3)]).toBe(word);
  });

  it("follows the letters when the parallax moves them", () => {
    const i = letters[0]!;
    const k = (1 - set.depth[i]!) * set.shift;
    const hit = hitTest(set, set.x[i]! + set.adv[i]! / 2 - k, set.y[i]! - set.size[i]! * 0.3, 1, 0);
    expect(set.word[hit]).toBe(word);
  });

  it("finds nothing far outside the rows", () => {
    expect(hitTest(set, 700, -500)).toBe(-1);
  });
});
