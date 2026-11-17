/**
 * Tiny motion helpers (no animation library): CSS keyframes in index.css do the moving; these
 * only keep an element on screen long enough for its exit animation to play.
 */
import { useEffect, useState } from "react";

export function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

export type Presence = "open" | "closing" | "closed";

/**
 * "open" while `open`; "closing" for `exitMs` after it turns false (so an exit animation can
 * run), then "closed". Under reduced motion it goes straight to "closed".
 */
export function usePresence(open: boolean, exitMs = 200): Presence {
  const [state, setState] = useState<Presence>(open ? "open" : "closed");
  useEffect(() => {
    if (open) {
      setState("open");
      return;
    }
    if (prefersReducedMotion()) {
      setState("closed");
      return;
    }
    setState((s) => (s === "closed" ? s : "closing"));
    const t = window.setTimeout(() => setState("closed"), exitMs);
    return () => window.clearTimeout(t);
  }, [open, exitMs]);
  if (open) return "open";
  return prefersReducedMotion() ? "closed" : state;
}

/** Whether a media query matches, kept up to date (false where matchMedia is missing). */
export function useMediaQuery(query: string): boolean {
  const get = () => {
    try {
      return window.matchMedia(query).matches;
    } catch {
      return false;
    }
  };
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    let mql: MediaQueryList;
    try {
      mql = window.matchMedia(query);
    } catch {
      return;
    }
    const on = () => setMatches(mql.matches);
    on();
    mql.addEventListener?.("change", on);
    return () => mql.removeEventListener?.("change", on);
  }, [query]);
  return matches;
}
