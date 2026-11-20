import { SHAPES, type Frame, type ShapeName } from "./shapes";

/**
 * TypeScape engine: rows of real course titles (the homepage chapel's sample,
 * /home/course-chapel.json) set across a canvas like courses of stone. A faint layer covers the
 * whole canvas; a strong layer is coloured by a shape field (shapes.ts), sampled on a coarse
 * grid every frame, so the figure moves while the letters stay put. The pointer brings a lens
 * that magnifies the letters under it; the title under the pointer is named in a label and a
 * click opens its course. Under reduced motion the picture is still (label and click still work).
 */

export interface CourseTitle {
  code: string;
  title: string;
}

let coursesOnce: Promise<CourseTitle[]> | null = null;

export function loadCourseTitles(): Promise<CourseTitle[]> {
  coursesOnce ??= fetch("/home/course-chapel.json")
    .then((r) => (r.ok ? r.json() : { courses: [] }))
    .then((d: { courses?: [string, string][] }) =>
      (d.courses ?? []).map(([code, title]) => ({ code, title })),
    )
    .catch(() => []);
  return coursesOnce;
}

interface Span {
  x0: number;
  x1: number;
  course: CourseTitle | null;
}

interface Row {
  y: number;
  spans: Span[];
}

export interface EngineOptions {
  shape: ShapeName;
  /** Horizontal centre of the figure as a fraction of the width (narrow screens: 0.5). */
  focus: number;
  /** Extra words woven into the titles (e.g. the student's interests), drawn heavier. */
  words: string[];
  reducedMotion: boolean;
  onOpen: (code: string) => void;
}

type RGB = readonly [number, number, number];
const INK: RGB = [17, 17, 17];
const MAROON: RGB = [128, 0, 0];
const GLASS: RGB = [190, 92, 92];
const CELL = 5; // CSS px per field sample
const LENS_R = 62;
const LENS_ZOOM = 1.6;

function mix(a: RGB, b: RGB, t: number): RGB {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function toneColor(tone: number): RGB {
  if (tone <= 1) return mix(INK, MAROON, Math.max(0, tone));
  return mix(MAROON, GLASS, Math.min(1, tone - 1));
}

/** A small seeded shuffle, so each shape has its own order of titles. */
function shuffled<T>(items: T[], seed: number): T[] {
  const out = items.slice();
  let s = seed >>> 0 || 1;
  for (let i = out.length - 1; i > 0; i--) {
    s = (s * 1664525 + 1013904223) >>> 0;
    const j = s % (i + 1);
    const tmp = out[i]!;
    out[i] = out[j]!;
    out[j] = tmp;
  }
  return out;
}

export class TypeScapeEngine {
  private ctx: CanvasRenderingContext2D;
  private faint = document.createElement("canvas");
  private strong = document.createElement("canvas");
  private work = document.createElement("canvas");
  private field = document.createElement("canvas");
  private rows: Row[] = [];
  private w = 0;
  private h = 0;
  private dpr = 1;
  private font = "";
  private rowH = 14;
  private raf = 0;
  private visible = true;
  private start = performance.now();
  private pointer: { x: number; y: number } | null = null;
  private hovered: Span | null = null;
  private disposed = false;
  private lastDraw = 0;
  private observers: { disconnect(): void }[] = [];

  constructor(
    private canvas: HTMLCanvasElement,
    private label: HTMLElement,
    private titles: CourseTitle[],
    private opts: EngineOptions,
  ) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no 2d context");
    this.ctx = ctx;
    const ro = new ResizeObserver(() => this.layout());
    ro.observe(canvas);
    const io = new IntersectionObserver((entries) => {
      this.visible = entries.some((e) => e.isIntersecting);
      if (this.visible) this.loop();
    });
    io.observe(canvas);
    this.observers.push(ro, io);
    canvas.addEventListener("pointermove", this.onMove);
    canvas.addEventListener("pointerleave", this.onLeave);
    canvas.addEventListener("click", this.onClick);
    document.addEventListener("visibilitychange", this.onVisibility);
    this.layout();
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    for (const o of this.observers) o.disconnect();
    this.canvas.removeEventListener("pointermove", this.onMove);
    this.canvas.removeEventListener("pointerleave", this.onLeave);
    this.canvas.removeEventListener("click", this.onClick);
    document.removeEventListener("visibilitychange", this.onVisibility);
  }

  private onVisibility = () => {
    if (!document.hidden) this.loop();
  };

  private layout() {
    const rect = this.canvas.getBoundingClientRect();
    const w = Math.max(1, Math.round(rect.width));
    const h = Math.max(1, Math.round(rect.height));
    if (w === this.w && h === this.h && this.rows.length) return;
    this.w = w;
    this.h = h;
    // Keep the four layers under ~40 MB: a big canvas gets a lower pixel ratio.
    const area = w * h;
    this.dpr = Math.min(window.devicePixelRatio || 1, area > 1_200_000 ? 1.25 : 2);
    for (const c of [this.canvas, this.faint, this.strong, this.work]) {
      c.width = Math.round(w * this.dpr);
      c.height = Math.round(h * this.dpr);
    }
    this.field.width = Math.ceil(w / CELL);
    this.field.height = Math.ceil(h / CELL);
    const size = w < 640 ? 10 : w < 1100 ? 11 : 12;
    this.rowH = Math.round(size * 1.28);
    this.font = `500 ${size}px Newsreader, "Times New Roman", serif`;
    this.setRows();
    this.draw(true);
  }

  private setRows() {
    const seed = [...this.opts.shape].reduce((s, ch) => s * 31 + ch.charCodeAt(0), 7);
    const pool: CourseTitle[] = shuffled(this.titles, seed);
    const words = this.opts.words.filter(Boolean);
    const faint = this.faint.getContext("2d")!;
    const strong = this.strong.getContext("2d")!;
    for (const c of [faint, strong]) {
      c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      c.clearRect(0, 0, this.w, this.h);
      c.font = this.font;
      c.textBaseline = "alphabetic";
    }
    faint.fillStyle = "rgba(17,17,17,0.085)";
    strong.fillStyle = "#ffffff";
    this.rows = [];
    let k = 0;
    const gap = this.rowH * 0.55;
    for (let y = this.rowH; y < this.h + this.rowH; y += this.rowH) {
      const row: Row = { y, spans: [] };
      let x = -((k * 37) % 90);
      while (x < this.w) {
        const useWord = words.length > 0 && (k + row.spans.length) % 11 === 5;
        const course = useWord ? null : (pool[k % Math.max(1, pool.length)] ?? null);
        const text = useWord
          ? (words[(k + row.spans.length) % words.length] ?? "").toUpperCase()
          : (course?.title ?? "Quarterly");
        k++;
        if (useWord) strong.font = this.font.replace("500", "700");
        const tw = strong.measureText(text).width;
        faint.fillText(text, x, y);
        strong.fillText(text, x, y);
        if (useWord) strong.font = this.font;
        row.spans.push({ x0: x, x1: x + tw, course });
        x += tw + gap;
      }
      this.rows.push(row);
    }
  }

  private frame(t: number): Frame {
    const narrow = this.w < 900;
    return { w: this.w, h: this.h, cx: this.w * (narrow ? 0.5 : this.opts.focus), t };
  }

  /** Samples the shape on the coarse grid: colour in RGB, strength in alpha. */
  private paintField(f: Frame) {
    const fc = this.field.getContext("2d")!;
    const cols = this.field.width;
    const rows = this.field.height;
    const img = fc.createImageData(cols, rows);
    const fn = SHAPES[this.opts.shape];
    let i = 0;
    for (let r = 0; r < rows; r++) {
      const y = r * CELL + CELL / 2;
      for (let c = 0; c < cols; c++) {
        const s = fn(c * CELL + CELL / 2, y, f);
        const [cr, cg, cb] = toneColor(s.tone);
        img.data[i] = cr;
        img.data[i + 1] = cg;
        img.data[i + 2] = cb;
        img.data[i + 3] = Math.round(Math.min(1, s.a) * 255);
        i += 4;
      }
    }
    fc.putImageData(img, 0, 0);
  }

  private draw(force = false) {
    const now = performance.now();
    if (!force && now - this.lastDraw < 33) return; // ~30 frames a second is plenty
    this.lastDraw = now;
    const t = this.opts.reducedMotion ? 8 : (now - this.start) / 1000;
    const f = this.frame(t);
    this.paintField(f);
    // Strong layer: white glyphs, recoloured and masked by the field.
    const wk = this.work.getContext("2d")!;
    wk.setTransform(1, 0, 0, 1, 0, 0);
    wk.globalCompositeOperation = "source-over";
    wk.clearRect(0, 0, this.work.width, this.work.height);
    const p = this.pointer;
    const par = p && !this.opts.reducedMotion ? (p.x / this.w - 0.5) * 6 : 0;
    const parY = p && !this.opts.reducedMotion ? (p.y / this.h - 0.5) * 4 : 0;
    wk.drawImage(this.strong, par * this.dpr, parY * this.dpr);
    wk.globalCompositeOperation = "source-in";
    wk.imageSmoothingEnabled = true;
    wk.drawImage(this.field, 0, 0, this.work.width, this.work.height);
    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.drawImage(this.faint, -par * 0.4 * this.dpr, 0);
    ctx.drawImage(this.work, 0, 0);
    if (p && !this.opts.reducedMotion) this.drawLens(p);
    if (this.hovered) this.drawHover(this.hovered, par, parY);
  }

  private drawLens(p: { x: number; y: number }) {
    const ctx = this.ctx;
    const d = this.dpr;
    const src = (LENS_R * 2) / LENS_ZOOM;
    ctx.save();
    ctx.beginPath();
    ctx.arc(p.x * d, p.y * d, LENS_R * d, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillStyle = "rgba(247,247,245,0.92)";
    ctx.fillRect((p.x - LENS_R) * d, (p.y - LENS_R) * d, LENS_R * 2 * d, LENS_R * 2 * d);
    for (const layer of [this.faint, this.work]) {
      ctx.drawImage(
        layer,
        (p.x - src / 2) * d,
        (p.y - src / 2) * d,
        src * d,
        src * d,
        (p.x - LENS_R) * d,
        (p.y - LENS_R) * d,
        LENS_R * 2 * d,
        LENS_R * 2 * d,
      );
    }
    ctx.restore();
    ctx.beginPath();
    ctx.arc(p.x * d, p.y * d, LENS_R * d, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(128,0,0,0.35)";
    ctx.lineWidth = 1 * d;
    ctx.stroke();
  }

  private drawHover(span: Span, par: number, parY: number) {
    if (!span.course) return;
    const row = this.rows.find((r) => r.spans.includes(span));
    if (!row) return;
    const ctx = this.ctx;
    const d = this.dpr;
    ctx.save();
    ctx.setTransform(d, 0, 0, d, 0, 0);
    ctx.font = this.font;
    ctx.fillStyle = "rgba(247,247,245,0.9)";
    ctx.fillRect(span.x0 + par - 2, row.y + parY - this.rowH + 3, span.x1 - span.x0 + 4, this.rowH);
    ctx.fillStyle = "#111111";
    ctx.fillText(span.course.title, span.x0 + par, row.y + parY);
    ctx.fillRect(span.x0 + par, row.y + parY + 2, span.x1 - span.x0, 1);
    ctx.restore();
  }

  /** The title under (x, y), if the figure is drawn there. */
  private hit(x: number, y: number): Span | null {
    const fn = SHAPES[this.opts.shape];
    const t = this.opts.reducedMotion ? 8 : (performance.now() - this.start) / 1000;
    if (fn(x, y, this.frame(t)).a < 0.3) return null;
    const row = this.rows.find((r) => y <= r.y + 3 && y > r.y - this.rowH + 3);
    return row?.spans.find((s) => s.course && x >= s.x0 && x <= s.x1) ?? null;
  }

  private onMove = (e: PointerEvent) => {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    this.pointer = { x, y };
    const span = this.hit(x, y);
    this.hovered = span;
    this.canvas.style.cursor = span ? "pointer" : "";
    if (span?.course) {
      this.label.replaceChildren();
      const strong = document.createElement("strong");
      strong.textContent = span.course.code;
      this.label.append(strong, ` · ${span.course.title}`);
      const lx = Math.min(Math.max(8, x + 14), this.w - 260);
      this.label.style.transform = `translate(${lx}px, ${Math.max(4, y - 40)}px)`;
      this.label.dataset.visible = "true";
    } else this.label.dataset.visible = "false";
    if (this.opts.reducedMotion) this.draw(true);
  };

  private onLeave = () => {
    this.pointer = null;
    this.hovered = null;
    this.label.dataset.visible = "false";
    this.canvas.style.cursor = "";
    this.draw(true);
  };

  private onClick = (e: MouseEvent) => {
    const rect = this.canvas.getBoundingClientRect();
    const span = this.hit(e.clientX - rect.left, e.clientY - rect.top);
    if (span?.course) this.opts.onOpen(span.course.code);
  };

  /** Starts (or keeps) the animation; a still picture under reduced motion. */
  loop() {
    if (this.disposed) return;
    if (this.opts.reducedMotion) {
      this.draw(true);
      return;
    }
    cancelAnimationFrame(this.raf);
    const tick = () => {
      if (this.disposed || !this.visible || document.hidden) return;
      this.draw();
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }
}
