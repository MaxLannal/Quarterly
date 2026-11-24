/**
 * Runs the homepage chapel: loads the drawing and titles, lays them out for the hero's size,
 * and turns the pointer (mouse, pen or fingers) into the camera, the lens, ripples and the hovered
 * title. Plain DOM and WebGL, no React state, so a frame never re-renders the page.
 */
import { type ChapelData, decodeField, type Field, isChapelData } from "./field";
import { CHAPEL_SIDE_QUERY, type GlyphSet, hitTest, layoutGlyphs, type Metrics, type Placement } from "./layout";
import {
  type Atlas,
  buildAtlas,
  canvasFallback,
  ChapelRenderer,
  FONT_FAMILY,
  type FrameState,
  measureMetrics,
  TRAIL,
} from "./renderer";

export const DATA_URL = "/home/course-chapel.json";

export type ChapelElements = {
  section: HTMLElement;
  canvas: HTMLCanvasElement;
  /** the small course-code label that follows the mouse */
  label: HTMLElement;
  /** the page's own controls; letters fade behind them and they get no lens */
  ui: HTMLElement;
};

type TrailPoint = { x: number; y: number; age: number; strength: number };

let dataPromise: Promise<ChapelData> | null = null;
function loadData(): Promise<ChapelData> {
  dataPromise ??= fetch(DATA_URL)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`chapel data: ${r.status}`))))
    .then((d: unknown) => {
      if (!isChapelData(d)) throw new Error("chapel data: unexpected shape");
      return d;
    })
    .catch((e: unknown) => {
      dataPromise = null;
      throw e;
    });
  return dataPromise;
}

const ease = (current: number, target: number, rate: number, dt: number) =>
  current + (target - current) * (1 - Math.exp(-rate * dt));

export class ChapelController {
  private el: ChapelElements;
  private onOpen: (code: string) => void;
  /** draw only when something changes: reduced motion, or a GPU too slow for the animation */
  private still: boolean;
  private slowFrames = { time: 0, count: 0 };
  private renderer: ChapelRenderer | null = null;
  private fallback = false;
  private data: ChapelData | null = null;
  private field: Field | null = null;
  private metrics: Metrics | null = null;
  private atlas: Atlas | null = null;
  private atlasChars = "";
  private set: GlyphSet | null = null;
  private size = { w: 0, h: 0 };
  private uiRight = 0;
  private clear: [number, number, number, number] = [-1e4, -1e4, -1e4, -1e4];
  private disposed = false;
  private raf = 0;
  private last = 0;
  private start = 0;
  private visible = true;
  private resizeObserver: ResizeObserver | null = null;
  private intersection: IntersectionObserver | null = null;
  private cleanups: (() => void)[] = [];

  // pointer state
  private pointer = { x: -1e4, y: -1e4, inside: false, kind: "mouse" as string, lastX: 0, lastY: 0, lastT: 0 };
  private cam = { x: 0, y: 0 };
  private lens = 0;
  /** where the lens is drawn: it follows the pointer with a little weight */
  private lensAt = { x: -1e4, y: -1e4 };
  private trail: TrailPoint[] = [];
  private hoverWord = -1;
  private trailBuf = new Float32Array(TRAIL * 4);

  // the night scene (HomePage's Day / Night switch), the two street lamps and the moon, all
  // painted in the letters by the shader
  private night = 0;
  private nightTarget = 0;
  private lamps: [number, number, number, number] = [-1e4, -1e4, -1e4, 0];
  private moon: [number, number, number] = [-1e4, -1e4, 1];

  constructor(el: ChapelElements, onOpen: (code: string) => void, reducedMotion: boolean) {
    this.el = el;
    this.onOpen = onOpen;
    this.still = reducedMotion;
  }

  async init(): Promise<void> {
    const data = await loadData();
    const chars = Array.from(new Set(data.courses.map(([, t]) => t).join("") + "·")).join("");
    await document.fonts.load(`600 64px ${FONT_FAMILY}`, chars);
    if (this.disposed) return;
    this.data = data;
    this.field = decodeField(data);
    this.metrics = measureMetrics();
    this.renderer = ChapelRenderer.create(this.el.canvas);
    if (!this.renderer) this.fallback = true;
    this.listen();
    this.relayout();
    this.start = performance.now();
    this.el.canvas.dataset.hover = "";
    this.el.canvas.dataset.state = "ready";
    this.el.canvas.dataset.renderer = this.renderer ? "webgl2" : "canvas";
    if (this.still || this.fallback) this.render();
    else this.loop();
  }

  dispose(): void {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.resizeObserver?.disconnect();
    this.intersection?.disconnect();
    for (const c of this.cleanups) c();
    this.renderer?.dispose();
    this.renderer = null;
  }

  /** for tests: the course under a point of the hero, or null */
  courseAt(x: number, y: number): string | null {
    if (!this.set || !this.data) return null;
    const i = hitTest(this.set, x, y, this.cam.x, this.cam.y);
    return i >= 0 ? (this.data.courses[this.set.word[i]!]?.[0] ?? null) : null;
  }

  private listen() {
    const { section, canvas } = this.el;
    const on = <K extends keyof HTMLElementEventMap>(
      target: HTMLElement,
      type: K,
      fn: (e: HTMLElementEventMap[K]) => void,
      opts?: AddEventListenerOptions,
    ) => {
      target.addEventListener(type, fn, opts);
      this.cleanups.push(() => target.removeEventListener(type, fn, opts));
    };
    on(section, "pointermove", (e) => {
      if (e.pointerType === "touch") return; // touches come through the touch events below
      this.move(e.clientX, e.clientY, e.pointerType, e.timeStamp);
    });
    on(section, "pointerleave", (e) => {
      if (e.pointerType !== "touch") this.leave();
    });
    on(section, "pointerdown", (e) => {
      if (e.pointerType === "touch") return;
      const p = this.local(e.clientX, e.clientY);
      if (!this.overUi(p.x, p.y)) this.addTrail(p.x, p.y, 1);
      this.kick();
    });
    on(section, "click", (e) => {
      if (this.hoverWord < 0 || !this.data) return;
      if ((e.target as Element | null)?.closest("a, button, input, form, label")) return;
      const code = this.data.courses[this.hoverWord]?.[0];
      if (code) this.onOpen(code);
    });
    const touch = (e: TouchEvent) => {
      const t = e.touches[0] ?? e.changedTouches[0];
      if (!t) return;
      if (e.type === "touchend" || e.type === "touchcancel") {
        if (e.touches.length === 0) this.leave();
        return;
      }
      this.move(t.clientX, t.clientY, "touch", e.timeStamp);
    };
    for (const type of ["touchstart", "touchmove", "touchend", "touchcancel"] as const) {
      on(section, type, touch, { passive: true });
    }
    const visibility = () => {
      if (!document.hidden) this.kick();
    };
    document.addEventListener("visibilitychange", visibility);
    this.cleanups.push(() => document.removeEventListener("visibilitychange", visibility));
    const lost = (e: Event) => {
      e.preventDefault();
      cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.renderer = null;
    };
    canvas.addEventListener("webglcontextlost", lost);
    this.cleanups.push(() => canvas.removeEventListener("webglcontextlost", lost));

    this.resizeObserver = new ResizeObserver(() => {
      this.relayout();
      if (this.still || this.fallback) this.render();
    });
    this.resizeObserver.observe(section);
    this.resizeObserver.observe(this.el.ui);
    this.intersection = new IntersectionObserver((entries) => {
      this.visible = entries.some((en) => en.isIntersecting);
      if (this.visible) this.kick();
    });
    this.intersection.observe(section);
  }

  private local(cx: number, cy: number) {
    const r = this.el.canvas.getBoundingClientRect();
    return { x: cx - r.left, y: cy - r.top };
  }

  private overUi(x: number, y: number): boolean {
    const [x0, y0, x1, y1] = this.clear;
    return x >= x0 - 8 && x <= x1 + 8 && y >= y0 - 8 && y <= y1 + 8;
  }

  private move(cx: number, cy: number, kind: string, t: number) {
    const p = this.local(cx, cy);
    const prev = this.pointer;
    const wasInside = prev.inside;
    this.pointer = { ...prev, x: p.x, y: p.y, inside: true, kind };
    if (this.overUi(p.x, p.y)) {
      this.pointer.inside = false;
      this.setHover(-1);
      this.kick();
      return;
    }
    const dx = p.x - prev.lastX;
    const dy = p.y - prev.lastY;
    const dist = Math.hypot(dx, dy);
    if (!wasInside) Object.assign(this.pointer, { lastX: p.x, lastY: p.y, lastT: t });
    else if (dist > 16) {
      const speed = dist / Math.max(8, t - prev.lastT); // px per ms
      this.addTrail(p.x, p.y, Math.min(1, Math.max(0.3, speed / 1.6)));
      Object.assign(this.pointer, { lastX: p.x, lastY: p.y, lastT: t });
    }
    if (this.set) {
      const i = hitTest(this.set, p.x, p.y, this.cam.x, this.cam.y);
      this.setHover(i);
    }
    this.kick();
  }

  private leave() {
    this.pointer.inside = false;
    this.setHover(-1);
    this.kick();
  }

  private addTrail(x: number, y: number, strength: number) {
    if (this.still) return;
    this.trail.push({ x, y, age: 0, strength });
    if (this.trail.length > TRAIL) this.trail.shift();
  }

  private setHover(glyph: number) {
    const word = glyph >= 0 && this.set ? this.set.word[glyph]! : -1;
    const { label, section, canvas } = this.el;
    if (word !== this.hoverWord) {
      this.hoverWord = word;
      const code = word >= 0 ? this.data?.courses[word]?.[0] : undefined;
      section.style.cursor = code ? "pointer" : "";
      canvas.dataset.hover = code ?? "";
      const title = word >= 0 ? this.data?.courses[word]?.[1] : undefined;
      if (code && title && this.pointer.kind !== "touch") {
        label.replaceChildren();
        const strong = document.createElement("strong");
        strong.className = "font-semibold";
        strong.textContent = code;
        label.append(strong, ` ${title}`);
        label.dataset.visible = "true";
      } else {
        label.dataset.visible = "false";
      }
      if (this.still || this.fallback) this.render();
    }
    if (word >= 0 && this.set) {
      // the label sits just above the line the title is on
      const row = this.set.rows.find((r) => glyph >= r.start && glyph < r.end);
      const top = (row ? row.y - row.size * 1.25 : this.pointer.y) - 34;
      const x = Math.max(4, Math.min(this.size.w - label.offsetWidth - 8, this.pointer.x + 12));
      label.style.transform = `translate(${Math.round(x)}px, ${Math.round(Math.max(4, top))}px)`;
    }
  }

  private measureClear() {
    const c = this.el.canvas.getBoundingClientRect();
    const u = this.el.ui.getBoundingClientRect();
    const pad = 20;
    this.clear = [u.left - c.left - pad, u.top - c.top - pad, u.right - c.left + pad, u.bottom - c.top + pad];
  }

  private relayout() {
    const { data, field, metrics } = this;
    if (!data || !field || !metrics) return;
    const rect = this.el.section.getBoundingClientRect();
    const w = Math.round(rect.width);
    const h = Math.round(rect.height);
    this.measureClear();
    if (w < 2 || h < 2) return;
    const placement: Placement = window.matchMedia(CHAPEL_SIDE_QUERY).matches ? "side" : "bottom";
    const uiRight = Math.round(this.clear[2]);
    if (this.set && w === this.size.w && h === this.size.h && placement === this.set.placement && uiRight === this.uiRight) {
      return;
    }
    this.size = { w, h };
    this.uiRight = uiRight;
    const set = layoutGlyphs({ width: w, height: h, data, field, metrics, placement, uiRight });
    this.set = set;
    this.placeLamps(set, data.chapel, w, h);
    this.el.canvas.dataset.glyphs = String(set.count);
    this.el.canvas.dataset.placement = set.placement;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    if (this.renderer) {
      const chars = set.charset.join("");
      if (!this.atlas || chars !== this.atlasChars) {
        this.atlas = buildAtlas(set.charset, metrics);
        this.atlasChars = chars;
      }
      this.renderer.resize(w, h, dpr);
      this.renderer.setGlyphs(set, this.atlas);
    } else if (this.fallback) {
      canvasFallback(this.el.canvas, set, w, h, dpr, this.clear);
    }
    this.setHover(-1);
  }

  /** Day (false) or the snowy night scene (true); the light changes over about two seconds. */
  setNight(on: boolean): void {
    this.nightTarget = on ? 1 : 0;
    if (this.still || this.fallback) {
      this.night = this.nightTarget;
      this.render();
    } else this.kick();
  }

  /** Two lamps flank the chapel on its ground line (kept on screen on a phone); the moon sits in
   * the open sky, clear of the Day / Night switch. */
  private placeLamps(set: GlyphSet, chapel: { x0: number; x1: number; y0: number; y1: number }, w: number, h: number) {
    const f = set.frame;
    const side = set.placement === "side";
    // the controls fade the letters behind them: the lamps stand clear of that area
    const uiRight = this.clear[2] + 70;
    const uiTop = this.clear[1] - 40;
    let ground = Math.min(h - 10, f.oy + f.h * Math.min(0.995, chapel.y1 + 0.012));
    if (!side) ground = Math.min(ground, uiTop);
    // on a phone the lamps stand above the controls, a little shorter so the switch stays clear
    const height = Math.max(120, Math.min(h * 0.36, 290, side ? ground - 30 : ground * 0.55));
    const clampX = (x: number) => Math.max(w * 0.07, Math.min(w * 0.93, x));
    let left = clampX(f.ox + f.w * (chapel.x0 - 0.035));
    if (side) left = Math.max(left, uiRight);
    this.lamps = [left, clampX(f.ox + f.w * (chapel.x1 + 0.035)), ground, height];
    const r = Math.max(26, Math.min(58, Math.min(w, h) * 0.055));
    this.moon = set.placement === "side" ? [w * 0.86, h * 0.2, r] : [w * 0.2, h * 0.12, r];
  }

  /** restart the frame loop after it stopped for being idle or hidden */
  private kick() {
    if (this.still || this.fallback || this.disposed || this.raf) return;
    this.last = 0;
    this.loop();
  }

  private loop = () => {
    this.raf = 0;
    if (this.disposed || !this.visible || document.hidden) return;
    const now = performance.now();
    const raw = this.last ? (now - this.last) / 1000 : 1 / 60;
    const dt = Math.min(0.05, raw);
    this.last = now;
    if (this.tooSlow(raw)) {
      // under about 20 frames a second the motion only stutters: keep the picture still
      this.still = true;
      this.el.canvas.dataset.still = "slow";
      this.render();
      return;
    }
    this.step(dt, (now - this.start) / 1000);
    // the parallax moves the letters under a still mouse: keep the highlight on what is drawn there
    if (this.set && this.pointer.inside && this.pointer.kind !== "touch") {
      this.setHover(hitTest(this.set, this.pointer.x, this.pointer.y, this.cam.x, this.cam.y));
    }
    this.render();
    this.raf = requestAnimationFrame(this.loop);
  };

  /** watches the first two seconds of frames */
  private tooSlow(dt: number): boolean {
    const w = this.slowFrames;
    if (w.time > 2) return false;
    w.time += dt;
    w.count++;
    return w.time > 2 && w.count < 40;
  }

  private step(dt: number, time: number) {
    const { w, h } = this.size;
    const p = this.pointer;
    let tx: number;
    let ty: number;
    if (p.inside && p.kind !== "touch") {
      tx = Math.max(-1, Math.min(1, (p.x / Math.max(1, w)) * 2 - 1));
      ty = Math.max(-1, Math.min(1, (p.y / Math.max(1, h)) * 2 - 1));
    } else {
      // a slow sway, so the depth shows on touch screens and before the mouse arrives
      tx = Math.sin(time * 0.15) * 0.3;
      ty = Math.sin(time * 0.11 + 1.3) * 0.2;
    }
    this.cam.x = ease(this.cam.x, tx, 3, dt);
    this.cam.y = ease(this.cam.y, ty, 3, dt);
    this.lens = ease(this.lens, p.inside ? 1 : 0, p.inside ? 9 : 5, dt);
    this.night = ease(this.night, this.nightTarget, 1.6, dt);
    if (this.lens < 0.02) this.lensAt = { x: p.x, y: p.y };
    else this.lensAt = { x: ease(this.lensAt.x, p.x, 16, dt), y: ease(this.lensAt.y, p.y, 16, dt) };
    for (const t of this.trail) t.age += dt;
    while (this.trail.length && this.trail[0]!.age > 1.2) this.trail.shift();
  }

  private render() {
    const set = this.set;
    if (!set) return;
    if (this.fallback || !this.renderer) return;
    const n = this.trail.length;
    for (let i = 0; i < n; i++) {
      const t = this.trail[i]!;
      this.trailBuf.set([t.x, t.y, t.age, t.strength], i * 4);
    }
    const motion = !this.still;
    const state: FrameState = {
      camX: motion ? this.cam.x : 0,
      camY: motion ? this.cam.y : 0,
      pointerX: this.lensAt.x,
      pointerY: this.lensAt.y,
      lens: motion ? this.lens : 0,
      trail: this.trailBuf,
      trailCount: motion ? n : 0,
      time: motion ? (performance.now() - this.start) / 1000 : 1e3,
      hover: this.hoverWord,
      clear: this.clear,
      motion,
      night: motion ? this.night : this.nightTarget,
      lamps: this.lamps,
      moon: this.moon,
    };
    this.renderer.draw(state);
  }
}
