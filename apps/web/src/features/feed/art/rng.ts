/** Small deterministic helpers for the generated art: the same seed always draws the same picture. */

/** Mulberry32: a tiny, fast, good-enough PRNG returning numbers in [0, 1). */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** FNV-1a hash of a string (for seeds and colours of things the API gave no seed for). */
export function hash(text: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export type Rand = () => number;

export const between = (r: Rand, lo: number, hi: number) => lo + (hi - lo) * r();
export const pick = <T,>(r: Rand, items: readonly T[]): T => items[Math.floor(r() * items.length) % items.length] as T;
export const round = (n: number) => Math.round(n * 10) / 10;
