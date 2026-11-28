import { useId, useLayoutEffect, useRef, useState, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import "./folder.css";

/*
 * The folder (docs/DESIGN.md "Simple light"; Max asked on 2026-11-27 for each quarter as a folder): a back panel
 * with a tab on its top-left that slopes down into the body, the files standing inside it, and a
 * light grey front pocket across the bottom whose top edge steps down from left to right. The files
 * tuck a few pixels behind the pocket, so they read as inside the folder; nothing they say is
 * covered. The planner draws each quarter as one (classes are its files); the homepage uses three.
 *
 * Shapes are SVG paths sized to the measured folder (one ResizeObserver per folder), used both as
 * the clip of the CSS-painted panels (so a panel can carry any gradient or art, and the pocket's
 * backdrop blur stops at its edge) and as a lit outline. Before the first measurement (and in
 * tests without ResizeObserver) the panels are plain rounded boxes.
 */

/** Tab height, pocket height and the pocket's step, in px (folder.css uses the same numbers). */
const TAB_H = 42;
const POCKET_H = 72;
const POCKET_STEP = 12;
const R = 22;

function backPath(w: number, h: number, tabW: number): string {
  const slope = 34;
  const tr = 16;
  return [
    `M0 ${tr}`,
    `A${tr} ${tr} 0 0 1 ${tr} 0`,
    `L${tabW} 0`,
    `C${tabW + slope / 2} 0 ${tabW + slope / 2} ${TAB_H} ${tabW + slope} ${TAB_H}`,
    `L${w - R} ${TAB_H}`,
    `A${R} ${R} 0 0 1 ${w} ${TAB_H + R}`,
    `L${w} ${h - R}`,
    `A${R} ${R} 0 0 1 ${w - R} ${h}`,
    `L${R} ${h}`,
    `A${R} ${R} 0 0 1 0 ${h - R}`,
    "Z",
  ].join(" ");
}

function pocketPath(w: number, stepX: number): string {
  const slope = 38;
  const r = 18;
  const h = POCKET_H;
  return [
    `M0 ${r}`,
    `A${r} ${r} 0 0 1 ${r} 0`,
    `L${stepX} 0`,
    `C${stepX + slope / 2} 0 ${stepX + slope / 2} ${POCKET_STEP} ${stepX + slope} ${POCKET_STEP}`,
    `L${w - r} ${POCKET_STEP}`,
    `A${r} ${r} 0 0 1 ${w} ${POCKET_STEP + r}`,
    `L${w} ${h - R}`,
    `A${R} ${R} 0 0 1 ${w - R} ${h}`,
    `L${R} ${h}`,
    `A${R} ${R} 0 0 1 0 ${h - R}`,
    "Z",
  ].join(" ");
}

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const measure = () => {
      const w = Math.round(el.offsetWidth);
      const h = Math.round(el.offsetHeight);
      setSize((s) => (s && s.w === w && s.h === h ? s : { w, h }));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

export type FolderTone = "smoke" | "ember" | "garnet" | "frost";

export interface GlassFolderProps extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  /** On the tab, top-left (for a quarter: its name). */
  tab: ReactNode;
  /** Top-right of the back panel, beside the tab (a count, a badge, a menu). */
  aside?: ReactNode;
  /** On the front pocket (a summary, an add button). Without it the folder has a slim pocket lip. */
  pocket?: ReactNode;
  /** The files. */
  children?: ReactNode;
  /** The back panel: white (`smoke`), ink-outlined for the current quarter (`ember`), warm grey (`garnet`) or cool (`frost`). */
  tone?: FolderTone;
  /** A drop target under a dragged file, or the folder in focus: its edge lights red. */
  active?: boolean;
  /** Tab width as a fraction of the folder (0-1). */
  tabRatio?: number;
  bodyClassName?: string;
}

export function GlassFolder({
  tab,
  aside,
  pocket,
  children,
  tone = "smoke",
  active = false,
  tabRatio = 0.5,
  className,
  bodyClassName,
  ...rest
}: GlassFolderProps) {
  const [ref, size] = useSize<HTMLDivElement>();
  const gid = useId().replace(/:/g, "");
  const tabW = size ? Math.max(Math.min(140, size.w - 48), Math.min(size.w - 64, Math.round(size.w * tabRatio))) : 0;
  const back = size ? backPath(size.w, size.h, tabW) : null;
  const pocketD = size ? pocketPath(size.w, Math.round(size.w * 0.42)) : null;
  return (
    <div
      ref={ref}
      data-tone={tone}
      data-active={active ? "true" : undefined}
      data-shaped={size ? "true" : undefined}
      data-spotlight=""
      className={cn("glass-folder", className)}
      style={size ? { ["--tab-w" as string]: `${tabW}px` } : undefined}
      {...rest}
    >
      <div aria-hidden="true" className="glass-folder-back" style={back ? { clipPath: `path("${back}")` } : undefined} />
      {back && size && (
        <svg aria-hidden="true" className="glass-folder-edge" width={size.w} height={size.h} viewBox={`0 0 ${size.w} ${size.h}`}>
          <defs>
            <linearGradient id={`fe-${gid}`} x1="0" y1="0" x2="0" y2={size.h} gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor="var(--folder-edge-top)" />
              <stop offset="0.35" stopColor="var(--folder-edge-mid)" />
              <stop offset="1" stopColor="var(--folder-edge-low)" />
            </linearGradient>
          </defs>
          <path d={back} fill="none" stroke={`url(#fe-${gid})`} strokeWidth="1" vectorEffect="non-scaling-stroke" transform="translate(0.5 0.5) scale(0.9993)" />
        </svg>
      )}
      <div className="glass-folder-tab">{tab}</div>
      {aside && <div className="glass-folder-aside">{aside}</div>}
      <div className={cn("glass-folder-body", bodyClassName)}>{children}</div>
      <div className="glass-folder-pocket" data-empty={pocket ? undefined : "true"}>
        <div aria-hidden="true" className="glass-folder-pocket-glass" style={pocketD ? { clipPath: `path("${pocketD}")` } : undefined} />
        {pocketD && size && (
          <svg aria-hidden="true" className="glass-folder-pocket-edge" width={size.w} height={POCKET_H} viewBox={`0 0 ${size.w} ${POCKET_H}`}>
            <path d={pocketD} fill="none" stroke="var(--folder-pocket-edge)" strokeWidth="1" transform="translate(0.5 0.5) scale(0.9993)" />
          </svg>
        )}
        {pocket && <div className="glass-folder-pocket-content">{pocket}</div>}
      </div>
    </div>
  );
}

/**
 * A file: a sheet of light glass with a folded top-right corner. The sheet is painted by
 * pseudo-elements, so the element itself keeps a normal box (focus rings, drag handles, hit areas).
 * Put a `.glass-file` class on any element (a link, a button, a dnd-kit draggable) or use this.
 */
export function GlassFile({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("glass-file", className)} {...rest}>
      {children}
    </div>
  );
}
