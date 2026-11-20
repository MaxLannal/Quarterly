/**
 * Draws the course-title chapel: one textured quad per letter, instanced, in WebGL2. The vertex
 * shader does all the motion (build-in, parallax, the sun moving over the carving, drifting clouds,
 * a passing glint, the pointer's lens and its short wake), so the CPU only updates a few uniforms
 * per frame. canvasFallback() draws the still picture where
 * WebGL2 is missing.
 */
import type { GlyphSet, Metrics } from "./layout";
import { MAROON, NEUTRAL, NIGHT_STONE, STILL_SUN, WEIGHTS } from "./palette";

/** Inter (already the page's body font, one variable file for every weight, so no extra
 * download): at 7px its even strokes hold far more colour than a serif's hairlines. Letters come
 * in three weights (palette WEIGHTS), heavier where the picture is darker. */
export const FONT_FAMILY = '"Inter Variable"';
const ATLAS_PX = 64;
const PAD = 0.18;
export const TRAIL = 24;
const FLOATS = 20;

export type Atlas = {
  canvas: HTMLCanvasElement;
  /** u0, v0, u1, v1 per entry (weight * charset length + character index) */
  uv: Float32Array;
  /** quad width per entry, em */
  quad: Float32Array;
  pad: number;
  ascent: number;
  cellHeight: number;
};

export function fontAt(px: number, weight = 1): string {
  return `${WEIGHTS[weight] ?? WEIGHTS[1]} ${px}px ${FONT_FAMILY}, system-ui, sans-serif`;
}

/** Advance widths from the real font (measured once per character and weight at 64px). */
export function measureMetrics(): Metrics {
  const ctx = document.createElement("canvas").getContext("2d");
  const caches = WEIGHTS.map(() => new Map<string, number>());
  if (!ctx) return { advance: () => 0.5 };
  return {
    advance(ch, weight = 1) {
      const cache = caches[weight] ?? caches[1]!;
      let w = cache.get(ch);
      if (w === undefined) {
        ctx.font = fontAt(ATLAS_PX, weight);
        w = ctx.measureText(ch).width / ATLAS_PX;
        cache.set(ch, w);
      }
      return w;
    },
  };
}

/**
 * White glyphs on transparent, one cell per character and weight, packed in shelves. Entry
 * `weight * charset.length + index` holds a character at a weight.
 */
export function buildAtlas(charset: string[], metrics: Metrics): Atlas {
  const canvas = document.createElement("canvas");
  const probe = canvas.getContext("2d");
  if (!probe) throw new Error("no 2d canvas");
  probe.font = fontAt(ATLAS_PX, 0);
  const m = probe.measureText("ÉgjQ");
  const ascent = Math.max(0.9, (m.fontBoundingBoxAscent || m.actualBoundingBoxAscent || 58) / ATLAS_PX);
  const descent = Math.max(0.28, (m.fontBoundingBoxDescent || m.actualBoundingBoxDescent || 18) / ATLAS_PX);
  const cellH = Math.ceil((ascent + descent + 2 * PAD) * ATLAS_PX);
  const entries: [string, number][] = [];
  for (let w = 0; w < WEIGHTS.length; w++) for (const ch of charset) entries.push([ch, w]);
  const widths = entries.map(([ch, w]) => Math.ceil((metrics.advance(ch, w) + 2 * PAD) * ATLAS_PX));
  const W = 2048;
  let x = 0;
  let y = 0;
  const pos: [number, number][] = [];
  for (const w of widths) {
    if (x + w > W) {
      x = 0;
      y += cellH;
    }
    pos.push([x, y]);
    x += w;
  }
  const H = y + cellH;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("no 2d canvas");
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#fff";
  ctx.textBaseline = "alphabetic";
  const uv = new Float32Array(entries.length * 4);
  const quad = new Float32Array(entries.length);
  entries.forEach(([ch, weight], i) => {
    const [cx, cy] = pos[i]!;
    const w = widths[i]!;
    ctx.font = fontAt(ATLAS_PX, weight);
    ctx.fillText(ch, cx + PAD * ATLAS_PX, cy + (PAD + ascent) * ATLAS_PX);
    uv[i * 4] = cx / W;
    uv[i * 4 + 1] = cy / H;
    uv[i * 4 + 2] = (cx + w) / W;
    uv[i * 4 + 3] = (cy + cellH) / H;
    quad[i] = w / ATLAS_PX;
  });
  return { canvas, uv, quad, pad: PAD, ascent, cellHeight: cellH / ATLAS_PX };
}

/** A GLSL function for a palette ramp, from the same stops the still picture uses. */
function rampGlsl(name: string, list: [number, [number, number, number]][]): string {
  const n = list.length;
  const f = (v: number) => v.toFixed(4);
  const colors = list.map(([, c]) => `vec3(${c.map(f).join(", ")})`).join(", ");
  const ts = list.map(([t]) => f(t)).join(", ");
  return `const vec3 ${name}_C[${n}] = vec3[${n}](${colors});
const float ${name}_T[${n}] = float[${n}](${ts});
vec3 ${name}(float t) {
  t = clamp(t, 0.0, 1.0);
  for (int i = 1; i < ${n}; i++) {
    if (t <= ${name}_T[i]) return mix(${name}_C[i - 1], ${name}_C[i], (t - ${name}_T[i - 1]) / (${name}_T[i] - ${name}_T[i - 1]));
  }
  return ${name}_C[${n - 1}];
}`;
}

const VERT = `#version 300 es
precision highp float;
#define TRAIL ${TRAIL}
layout(location=0) in vec2 aCorner;
layout(location=1) in vec4 aPos;    // x, baseline y, font size, depth
layout(location=2) in vec4 aLook;   // tone, maroon, glass, alpha
layout(location=3) in vec4 aUV;
layout(location=4) in vec4 aMeta;   // quad width (em), course index, delay (s), advance (em)
layout(location=5) in vec4 aRelief; // slope of the carving (gx, gy), how much it shades, snowy

uniform vec2 uView;
uniform vec2 uCam;
uniform float uShift;
uniform vec4 uPointer;              // x, y, lens strength, radius
uniform vec4 uTrail[TRAIL];         // x, y, age (s), strength
uniform int uTrailCount;
uniform float uTime;
uniform float uHover;
uniform vec3 uHoverColor;
uniform vec4 uClear;
uniform float uFeather;
uniform int uPass;                  // 0 shadow, 1 letters, 2 lifted letters on top
uniform vec3 uCell;                 // pad, ascent, cell height (em)
uniform float uMotion;              // 0 under reduced motion: no movement and no changing light
uniform float uNight;               // 0 day .. 1 the snowy night scene
uniform vec4 uLamps;                // the two street lamps: x of each, the ground (y), height (px)
uniform vec3 uMoon;                 // the moon at night: x, y, radius (px)

out vec2 vUV;
out vec4 vColor;

${rampGlsl("maroonRamp", MAROON)}
${rampGlsl("neutralRamp", NEUTRAL)}
${rampGlsl("nightStoneRamp", NIGHT_STONE)}

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = p * 2.03 + 17.1;
    a *= 0.5;
  }
  return v;
}

void hide() { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); vColor = vec4(0.0); vUV = vec2(0.0); }

// A street lamp drawn in letters: an iron post, collar and base, a glass lantern and its cap.
// Returns how much of it is iron; \`glass\` says how much is the lantern's glass.
float lampOne(vec2 c, float lx, float gy, float H, out float glass) {
  glass = 0.0;
  if (H < 1.0) return 0.0;
  float dx = abs(c.x - lx);
  float y = gy - c.y;
  float iron = 0.0;
  if (y > 0.0 && y < H * 0.08 && dx < H * (0.095 - y / H * 0.5)) iron = 1.0;
  if (y > 0.0 && y < H * 0.77 && dx < H * 0.033) iron = 1.0;
  if (abs(y - H * 0.6) < H * 0.016 && dx < H * 0.058) iron = 1.0;
  if (abs(y - H * 0.765) < H * 0.016 && dx < H * 0.088) iron = 1.0;
  float ly = (y - H * 0.778) / (H * 0.15);
  if (ly >= 0.0 && ly <= 1.0 && dx < H * (0.064 + 0.026 * ly)) {
    glass = 1.0;
    // the lantern's frame: a mullion down the middle
    if (dx < H * 0.008) { glass = 0.0; iron = 1.0; }
  }
  float cy = (y - H * 0.928) / (H * 0.075);
  if (cy >= 0.0 && cy <= 1.0 && dx < H * 0.11 * (1.0 - cy)) iron = 1.0;
  if (abs(y - H * 1.02) < H * 0.016 && dx < H * 0.016) iron = 1.0;
  return iron;
}

// Snow falling, as a brightness at point c: three depths of flakes in columns, each flake
// drifting down at its own pace and swaying a little.
float snowfall(vec2 c, float t) {
  float s = 0.0;
  float period = uView.y + 80.0;
  for (int layer = 0; layer < 3; layer++) {
    float fl = float(layer);
    float cell = 30.0 + fl * 20.0;
    float size = 5.5 + fl * 2.8;
    float col = floor(c.x / cell);
    float r = hash(vec2(col, fl * 7.13 + 1.0));
    float r2 = hash(vec2(col * 1.7 + 3.0, fl + 3.1));
    float speed = (16.0 + fl * 14.0) * (0.75 + 0.5 * r2);
    for (int k = 0; k < 2; k++) {
      float ph = fract(r + float(k) * 0.5);
      float fy = mod(t * speed + ph * period, period) - 40.0;
      float fx = (col + 0.5 + (r2 - 0.5) * 0.6) * cell + sin(t * 0.55 + r * 6.28 + float(k) * 2.0) * (5.0 + fl * 3.0);
      vec2 d = (c - vec2(fx, fy)) / size;
      s = max(s, exp(-dot(d, d)));
    }
  }
  return s;
}

void main() {
  float size = aPos.z;
  float depth = aPos.w;
  vec2 p = aPos.xy;
  float alpha = aLook.w;
  float scale = 1.0;

  // build-in: the courses of letters settle into place from the ground up
  float t = clamp((uTime - aMeta.z) / 0.5, 0.0, 1.0);
  float e = 1.0 - pow(1.0 - t, 3.0);
  p.y -= (1.0 - e) * size * 0.8;
  alpha *= e;
  scale *= mix(0.8, 1.0, e);

  // parallax: near letters move most
  float k = (1.0 - depth) * uShift * uMotion;
  p += vec2(-uCam.x * k, -uCam.y * k * 0.5);
  vec2 c = p + vec2(aMeta.w * 0.5, -0.33) * size;

  // Light that changes on its own, slowly. The sun swings across the sky over about two
  // minutes, so the carving catches it from one side and then the other: lit faces go towards
  // white, faces turned away towards black. Clouds drift right on a slow wind, white with a
  // slightly darker rim, and their shadows cross the land. Now and then a soft glint of light
  // passes over the stone, and the great window glows and dims a little, like light through glass.
  float sky = smoothstep(0.85, 0.98, depth);
  float sunSide = uMotion > 0.5 ? sin(uTime * 0.05) : ${STILL_SUN.toFixed(3)};
  vec3 L = normalize(vec3(sin(sunSide * 0.9) * 0.8, -0.5, 0.55));
  vec3 n = normalize(vec3(-aRelief.x * 5.0, -aRelief.y * 5.0, 1.0));
  float facing = dot(n, L) - L.z;
  float relief = facing * 0.4 * aRelief.z;

  vec2 wind = vec2(uTime * 7.0, uTime * 1.2);
  float f = fbm((c - wind) / 520.0);
  float cloud = smoothstep(0.52, 0.7, f);
  float rim = smoothstep(0.44, 0.52, f) * (1.0 - smoothstep(0.52, 0.6, f));
  float shade = smoothstep(0.5, 0.74, fbm((c - wind + vec2(160.0, -220.0)) / 520.0));

  float cycle = mod(uTime, 26.0);
  float sweep = cycle / 14.0 * (uView.x + uView.y * 0.57 + 900.0) - 450.0;
  float sheen = exp(-pow((dot(c, vec2(0.82, 0.57)) - sweep) / 110.0, 2.0)) * (1.0 - smoothstep(13.0, 14.0, cycle));
  sheen *= aRelief.z * (0.35 + 0.65 * clamp(facing * 3.0 + 0.5, 0.0, 1.0)) * uMotion;

  float glow = aLook.z * (0.55 + 0.45 * noise(c / 38.0 + vec2(uTime * 0.12, 0.0))) * (1.0 - shade * 0.6);

  float tone = aLook.x + (relief - shade * 0.12 + sheen * 0.15) * (1.0 - sky) + glow * 0.2;
  tone = clamp(tone, 0.0, 1.0);
  // the stone is cut into a few clear steps of red, like the planes of a print, so light and shade
  // never smear into each other
  float steps = tone * 7.0;
  tone = mix(tone, (floor(steps) + smoothstep(0.25, 0.75, fract(steps))) / 7.0, aLook.y);
  alpha *= mix(1.0, 1.0 - 0.75 * cloud + rim * 1.1, sky);

  // the pointer's lens lifts and magnifies the letters under it, like a glass over the page
  vec2 d = c - uPointer.xy;
  float r2 = dot(d, d) / (uPointer.w * uPointer.w);
  float lift = exp(-r2 * 2.2) * uPointer.z;
  // a fisheye: letters spread about as much as they grow, so the magnified ones stay apart
  vec2 push = d * exp(-r2 * 1.5) * uPointer.z;
  // a short wake: letters the pointer has just passed stay a little raised, then settle
  for (int i = 0; i < TRAIL; i++) {
    if (i >= uTrailCount) break;
    vec4 tp = uTrail[i];
    vec2 q = c - tp.xy;
    float near = exp(-dot(q, q) / (uPointer.w * uPointer.w * 0.3)) * exp(-tp.z * 3.5) * tp.w;
    lift = max(lift, near * 0.4);
  }

  // the page's controls: letters behind them fade away
  vec2 lo = smoothstep(uClear.xy - uFeather, uClear.xy + uFeather * 0.25, c);
  vec2 hi = 1.0 - smoothstep(uClear.zw - uFeather * 0.25, uClear.zw + uFeather, c);
  float clear = lo.x * lo.y * hi.x * hi.y;
  alpha *= mix(1.0, 0.07, clear);
  lift *= 1.0 - clear;
  push *= 1.0 - clear;
  // edges of the hero melt into the page
  alpha *= smoothstep(0.0, 28.0, c.y) * (1.0 - smoothstep(uView.y - 72.0, uView.y - 4.0, c.y));

  float hov = (aMeta.y >= 0.0 && abs(aMeta.y - uHover) < 0.5) ? 1.0 - clear : 0.0;

  // lifted letters get a little deeper and fully opaque; the hovered title turns ink
  tone -= 0.06 * clamp(lift, 0.0, 1.0);
  vec3 col = mix(neutralRamp(tone), maroonRamp(tone), aLook.y);
  // The fades behind the page's controls and at the hero's edges, for letters drawn fully opaque.
  float fade = smoothstep(0.0, 28.0, c.y) * (1.0 - smoothstep(uView.y - 72.0, uView.y - 4.0, c.y))
    * mix(1.0, 0.07, clear);
  // The two street lamps, painted in the letters by day and by night.
  float glassA; float glassB;
  float iron = max(lampOne(c, uLamps.x, uLamps.z, uLamps.w, glassA), lampOne(c, uLamps.y, uLamps.z, uLamps.w, glassB));
  float glass = max(glassA, glassB);
  float lampAny = max(iron, glass);
  if (uNight > 0.001) {
    // A winter night. The sky's letters turn deep blue (darker high up), a few twinkle as stars,
    // a disc of pale letters is the moon; the stone is moonlit, the trees frosted, the lawn and
    // paths under snow; the great window glows warm.
    float hy = clamp(c.y / max(1.0, uView.y), 0.0, 1.0);
    vec3 skyCol = mix(vec3(0.02, 0.03, 0.11), vec3(0.13, 0.12, 0.32), smoothstep(0.0, 0.9, hy));
    float md = length(c - uMoon.xy) / max(1.0, uMoon.z);
    float moon = 1.0 - smoothstep(0.9, 1.0, md);
    float halo = exp(-pow(max(0.0, md - 1.0) * 1.3, 2.0)) * (1.0 - moon);
    skyCol = mix(skyCol, vec3(0.5, 0.53, 0.82), halo * 0.75);
    skyCol = mix(skyCol, vec3(1.0, 0.95, 0.78), moon);
    float h1 = hash(aPos.xy * 0.731);
    float star = step(0.972, h1) * (1.0 - moon) * (1.0 - halo)
      * (0.65 + 0.35 * sin(uTime * (0.9 + h1 * 2.6) + h1 * 60.0) * uMotion);
    skyCol = mix(skyCol, vec3(1.0, 0.93, 0.72), clamp(star, 0.0, 1.0));
    vec3 trees = mix(vec3(0.08, 0.11, 0.24), vec3(0.3, 0.36, 0.6), tone);
    vec3 snow = mix(vec3(0.78, 0.84, 0.96), vec3(0.95, 0.97, 1.0), clamp(tone + 0.2, 0.0, 1.0));
    vec3 nc = mix(trees, nightStoneRamp(tone * 0.88), aLook.y);
    // under snow: the lawn and the paths, and everything in front of the chapel's ground line
    float ground = smoothstep(uLamps.z - 24.0, uLamps.z + 16.0, c.y) * step(1.0, uLamps.w);
    float snowy = max(aRelief.w, ground) * (1.0 - aLook.y);
    nc = mix(nc, snow, snowy);
    nc = mix(nc, skyCol, sky);
    nc = mix(nc, vec3(1.0, 0.72, 0.34), clamp(aLook.z * 1.4, 0.0, 0.9));
    // the lamps' light: an amber halo round each lantern and an orange pool on the snow below
    float flicker = 0.93 + 0.07 * sin(uTime * 9.0) * sin(uTime * 2.3 + 1.0) * uMotion;
    float light = 0.0;
    float pool = 0.0;
    for (int i = 0; i < 2; i++) {
      float lx = i == 0 ? uLamps.x : uLamps.y;
      vec2 q = (c - vec2(lx, uLamps.z - uLamps.w * 0.85)) / (uLamps.w * 0.42);
      light += exp(-dot(q, q));
      vec2 p2 = (c - vec2(lx, uLamps.z)) / vec2(uLamps.w * 0.75, uLamps.w * 0.2);
      pool += exp(-dot(p2, p2));
    }
    light = clamp(light, 0.0, 1.0) * flicker;
    pool = clamp(pool, 0.0, 1.0) * flicker;
    nc = mix(nc, vec3(1.0, 0.62, 0.24), light * 0.8);
    nc = mix(nc, vec3(1.0, 0.6, 0.28), pool * mix(0.45, 0.92, snowy));
    col = mix(col, nc, uNight);
    // the sky's letters fill in at night (bigger and nearly opaque), so the sky reads dark
    alpha = mix(alpha, max(alpha, 0.97 * fade), uNight * sky);
    alpha = mix(alpha, max(alpha, light * 0.9 * fade), uNight * (1.0 - sky));
    // overlapping letters make a dark field; the moon and the stars stay crisp
    scale *= 1.0 + 0.7 * uNight * sky * (1.0 - max(moon, star));
  }
  if (lampAny > 0.0) {
    // cast iron: near black by day; at night dark, catching the lantern's light near the top
    float lit = clamp(1.0 - abs(c.y - (uLamps.z - uLamps.w * 0.8)) / (uLamps.w * 0.5), 0.0, 1.0);
    vec3 ironCol = mix(vec3(0.09, 0.07, 0.07), mix(vec3(0.05, 0.05, 0.1), vec3(0.42, 0.22, 0.08), lit * 0.7), uNight);
    float glow = 0.9 + 0.1 * sin(uTime * 7.0 + 1.3) * uMotion;
    vec3 glassCol = mix(vec3(0.85, 0.66, 0.36), vec3(1.0, 0.66, 0.2) * glow, uNight);
    col = mix(col, ironCol, iron);
    col = mix(col, glassCol, glass);
    alpha = mix(alpha, 0.98 * fade, lampAny);
    // the lamp's letters overlap into a solid silhouette
    scale *= 1.0 + 0.45 * lampAny;
  }
  if (uNight > 0.001) {
    // snowflakes: bright letters that drift down through the sky, lifted a little so they glow
    // over their neighbours; near a lamp they catch its orange light
    float flake = snowfall(c, uTime) * uNight * (1.0 - clear);
    vec2 qa = (c - vec2(uLamps.x, uLamps.z - uLamps.w * 0.85)) / (uLamps.w * 0.6);
    vec2 qb = (c - vec2(uLamps.y, uLamps.z - uLamps.w * 0.85)) / (uLamps.w * 0.6);
    float warm = clamp(exp(-dot(qa, qa)) + exp(-dot(qb, qb)), 0.0, 1.0);
    col = mix(col, mix(vec3(0.97, 0.98, 1.0), vec3(1.0, 0.8, 0.5), warm), flake);
    alpha = mix(alpha, 0.98, flake * fade);
    lift = max(lift, flake * 0.45);
  }
  col = mix(col, uHoverColor, hov);
  alpha = mix(alpha, 1.0, clamp(max(lift * 1.4, hov), 0.0, 1.0) * e);

  float rise = (min(lift, 1.2) * 1.1 + hov * 0.12) * uMotion;
  scale *= 1.0 + rise;
  p += push * uMotion;

  if (uPass == 0) {
    float s = rise + hov * 0.25;
    if (s < 0.03 || alpha < 0.02) { hide(); return; }
    p += vec2(s * 2.0, 2.0 + s * 6.0);
    col = vec3(0.07, 0.02, 0.03);
    alpha = 0.2 * min(1.0, s) * e;
    scale *= 1.04;
  } else if (uPass == 2) {
    float s = smoothstep(0.12, 0.35, rise + hov);
    if (s < 0.01) { hide(); return; }
    alpha *= s;
  }

  vec2 center = p + vec2(aMeta.w * 0.5, -0.33) * size;
  vec2 origin = p + vec2(-uCell.x, -(uCell.x + uCell.y)) * size;
  vec2 quad = vec2(aMeta.x, uCell.z) * size;
  vec2 pos = center + (origin + aCorner * quad - center) * scale;
  vec2 clip = pos / uView * 2.0 - 1.0;
  gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
  vUV = mix(aUV.xy, aUV.zw, aCorner);
  vColor = vec4(col, alpha);
}`;

const FRAG = `#version 300 es
precision mediump float;
uniform sampler2D uAtlas;
in vec2 vUV;
in vec4 vColor;
out vec4 outColor;
void main() {
  // a little gamma, so small letters keep their ink after mipmapping
  float a = pow(texture(uAtlas, vUV).a, 0.75) * vColor.a;
  if (a < 0.004) discard;
  outColor = vec4(vColor.rgb * a, a);
}`;

export type FrameState = {
  camX: number;
  camY: number;
  pointerX: number;
  pointerY: number;
  lens: number;
  trail: Float32Array; // TRAIL * 4
  trailCount: number;
  time: number;
  hover: number;
  clear: [number, number, number, number];
  motion: boolean;
  /** 0 day .. 1 the snowy night scene */
  night: number;
  /** the two street lamps: x of each, the ground (y), their height; CSS px */
  lamps: [number, number, number, number];
  /** the moon at night: x, y, radius; CSS px */
  moon: [number, number, number];
};

function compile(gl: WebGL2RenderingContext, type: number, src: string): WebGLShader {
  const s = gl.createShader(type);
  if (!s) throw new Error("shader");
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(s);
    gl.deleteShader(s);
    throw new Error(`shader: ${log ?? ""}`);
  }
  return s;
}

/**
 * Whether WebGL here runs on the CPU. Asked on a scratch canvas, so the real one can still get a
 * 2D context for the still picture.
 */
function softwareWebGL(): boolean {
  const gl = document.createElement("canvas").getContext("webgl2");
  if (!gl) return false;
  const info = gl.getExtension("WEBGL_debug_renderer_info");
  const name = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "";
  gl.getExtension("WEBGL_lose_context")?.loseContext();
  return /swiftshader|llvmpipe|softpipe|software|basic render driver/i.test(name);
}

export class ChapelRenderer {
  private gl: WebGL2RenderingContext;
  private program: WebGLProgram;
  private vao: WebGLVertexArrayObject;
  private instances: WebGLBuffer;
  private texture: WebGLTexture;
  private u: Record<string, WebGLUniformLocation | null> = {};
  private count = 0;
  private view: [number, number] = [1, 1];
  private set: GlyphSet | null = null;
  private atlas: Atlas | null = null;

  static create(canvas: HTMLCanvasElement): ChapelRenderer | null {
    try {
      if (softwareWebGL()) return null;
      // A software renderer (no GPU: some VMs, remote desktops, headless test browsers) manages a
      // frame or two a second here; those get the still picture instead.
      const gl = canvas.getContext("webgl2", {
        antialias: false,
        premultipliedAlpha: true,
        alpha: true,
        failIfMajorPerformanceCaveat: true,
      });
      return gl ? new ChapelRenderer(gl) : null;
    } catch {
      return null;
    }
  }

  private constructor(gl: WebGL2RenderingContext) {
    this.gl = gl;
    const program = gl.createProgram();
    if (!program) throw new Error("program");
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERT));
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) ?? "link");
    this.program = program;
    for (const name of [
      "uView", "uCam", "uShift", "uPointer", "uTrail", "uTrailCount", "uTime", "uHover",
      "uHoverColor", "uClear", "uFeather", "uPass", "uCell", "uMotion", "uAtlas",
      "uNight", "uLamps", "uMoon",
    ]) {
      this.u[name] = gl.getUniformLocation(program, name);
    }
    const vao = gl.createVertexArray();
    const corners = gl.createBuffer();
    const instances = gl.createBuffer();
    const texture = gl.createTexture();
    if (!vao || !corners || !instances || !texture) throw new Error("buffers");
    this.vao = vao;
    this.instances = instances;
    this.texture = texture;
    gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, corners);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, instances);
    for (let loc = 1; loc <= 5; loc++) {
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, FLOATS * 4, (loc - 1) * 16);
      gl.vertexAttribDivisor(loc, 1);
    }
    gl.bindVertexArray(null);
  }

  get context(): WebGL2RenderingContext {
    return this.gl;
  }

  setGlyphs(set: GlyphSet, atlas: Atlas): void {
    const gl = this.gl;
    if (this.atlas !== atlas) {
      gl.bindTexture(gl.TEXTURE_2D, this.texture);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, atlas.canvas);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      this.atlas = atlas;
    }
    const data = new Float32Array(set.count * FLOATS);
    for (let i = 0; i < set.count; i++) {
      const o = i * FLOATS;
      const g = set.weight[i]! * set.charset.length + set.glyph[i]!;
      data[o] = set.x[i]!;
      data[o + 1] = set.y[i]!;
      data[o + 2] = set.size[i]!;
      data[o + 3] = set.depth[i]!;
      data[o + 4] = set.look[i * 4]!;
      data[o + 5] = set.look[i * 4 + 1]!;
      data[o + 6] = set.look[i * 4 + 2]!;
      data[o + 7] = set.look[i * 4 + 3]!;
      data[o + 8] = atlas.uv[g * 4]!;
      data[o + 9] = atlas.uv[g * 4 + 1]!;
      data[o + 10] = atlas.uv[g * 4 + 2]!;
      data[o + 11] = atlas.uv[g * 4 + 3]!;
      data[o + 12] = atlas.quad[g]!;
      data[o + 13] = set.word[i]!;
      data[o + 14] = set.delay[i]!;
      data[o + 15] = set.adv[i]! / set.size[i]!;
      data[o + 16] = set.relief[i * 4]!;
      data[o + 17] = set.relief[i * 4 + 1]!;
      data[o + 18] = set.relief[i * 4 + 2]!;
      data[o + 19] = set.relief[i * 4 + 3]!;
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.instances);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    this.count = set.count;
    this.set = set;
  }

  resize(cssW: number, cssH: number, dpr: number): void {
    const canvas = this.gl.canvas as HTMLCanvasElement;
    const w = Math.max(1, Math.round(cssW * dpr));
    const h = Math.max(1, Math.round(cssH * dpr));
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
    this.view = [cssW, cssH];
  }

  draw(s: FrameState): void {
    const gl = this.gl;
    const set = this.set;
    const atlas = this.atlas;
    gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    if (!set || !atlas || this.count === 0) return;
    gl.useProgram(this.program);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    const u = this.u;
    gl.uniform1i(u.uAtlas!, 0);
    gl.uniform2f(u.uView!, this.view[0], this.view[1]);
    gl.uniform2f(u.uCam!, s.camX, s.camY);
    gl.uniform1f(u.uShift!, set.shift);
    gl.uniform4f(u.uPointer!, s.pointerX, s.pointerY, s.lens, set.radius);
    gl.uniform4fv(u.uTrail!, s.trail);
    gl.uniform1i(u.uTrailCount!, s.trailCount);
    gl.uniform1f(u.uTime!, s.time);
    gl.uniform1f(u.uHover!, s.hover);
    // the hovered title: ink by day, lamp-light amber at night
    const n = s.night;
    gl.uniform3f(u.uHoverColor!, 0.067 + (1 - 0.067) * n, 0.067 + (0.7 - 0.067) * n, 0.067 + (0.3 - 0.067) * n);
    gl.uniform1f(u.uNight!, n);
    gl.uniform4f(u.uLamps!, ...s.lamps);
    gl.uniform3f(u.uMoon!, ...s.moon);
    gl.uniform4f(u.uClear!, ...s.clear);
    gl.uniform1f(u.uFeather!, 56);
    gl.uniform3f(u.uCell!, atlas.pad, atlas.ascent, atlas.cellHeight);
    gl.uniform1f(u.uMotion!, s.motion ? 1 : 0);
    gl.bindVertexArray(this.vao);
    for (const pass of [0, 1, 2]) {
      gl.uniform1i(u.uPass!, pass);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.count);
    }
    gl.bindVertexArray(null);
  }

  dispose(): void {
    const gl = this.gl;
    gl.deleteBuffer(this.instances);
    gl.deleteTexture(this.texture);
    gl.deleteVertexArray(this.vao);
    gl.deleteProgram(this.program);
  }
}

/** The still picture in plain 2D canvas, for browsers without WebGL2 or without a GPU. */
export function canvasFallback(
  canvas: HTMLCanvasElement,
  set: GlyphSet,
  cssW: number,
  cssH: number,
  dpr: number,
  clear: [number, number, number, number],
): boolean {
  const ctx = canvas.getContext("2d");
  if (!ctx) return false;
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  ctx.textBaseline = "alphabetic";
  for (const row of set.rows) {
    let current = -1;
    for (let i = row.start; i < row.end; i++) {
      if (set.weight[i] !== current) {
        current = set.weight[i]!;
        ctx.font = fontAt(row.size, current);
      }
      const [r, g, b, a] = [set.rgba[i * 4]!, set.rgba[i * 4 + 1]!, set.rgba[i * 4 + 2]!, set.rgba[i * 4 + 3]!];
      const x = set.x[i]!;
      const y = set.y[i]!;
      const behindUi = x > clear[0] && x < clear[2] && y > clear[1] && y < clear[3];
      const edge = Math.min(1, Math.max(0, y / 28)) * Math.min(1, Math.max(0, (cssH - y) / 72)) * (behindUi ? 0.07 : 1);
      ctx.fillStyle = `rgba(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)},${(a * edge).toFixed(3)})`;
      ctx.fillText(set.charset[set.glyph[i]!]!, x, y);
    }
  }
  return true;
}
