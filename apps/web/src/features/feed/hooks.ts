/** Small hooks for the feed: on-screen detection, reduced motion, and the floating-words registry. */
import { useEffect, useState, useSyncExternalStore } from "react";
import { useMediaQuery } from "@/lib/motion";

export function useReducedMotion(): boolean {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}

/** Whether the element is on screen (true where IntersectionObserver is missing). */
export function useInView<T extends Element>(rootMargin = "0px"): [(el: T | null) => void, boolean] {
  const [el, setEl] = useState<T | null>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver(([entry]) => setInView(Boolean(entry?.isIntersecting)), { rootMargin });
    observer.observe(el);
    return () => observer.disconnect();
  }, [el, rootMargin]);
  return [setEl, inView];
}

// ------------------------------------------------------------------ floating words registry

/** The words of the cards on screen, for the background layer of floating words. */
const visible = new Map<string, readonly string[]>();
const listeners = new Set<() => void>();
let snapshot: readonly string[] = [];

function publish() {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const words of visible.values())
    for (const w of words) {
      const key = w.toLowerCase();
      if (!seen.has(key)) {
        seen.add(key);
        out.push(w);
      }
    }
  snapshot = out;
  for (const l of listeners) l();
}

export function useVisibleWords(): readonly string[] {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => snapshot,
    () => snapshot,
  );
}

/** While `active`, the card's words join the floating layer. */
export function useRegisterWords(id: string, words: readonly string[], active: boolean): void {
  const key = words.join("|");
  useEffect(() => {
    if (!active || !key) return;
    visible.set(id, key.split("|"));
    publish();
    return () => {
      visible.delete(id);
      publish();
    };
  }, [id, key, active]);
}
