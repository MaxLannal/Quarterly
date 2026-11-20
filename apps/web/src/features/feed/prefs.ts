/**
 * The feed's choices kept in this browser: the focus categories when logged out (or while the
 * profile cannot be reached), saved items, hidden items and "show less like this" weights.
 * Nothing here leaves the browser except the focus, which a logged-in student's profile keeps.
 */
import { readJson, removeKey, writeJson } from "@/lib/storage";

const FOCUS = "quarterly.feed.focus";
const PENDING = "quarterly.feed.focus.pending";
const SAVED = "quarterly.feed.saved";
const HIDDEN = "quarterly.feed.hidden";
const LESS = "quarterly.feed.less";

const MAX_SAVED = 200;
const MAX_HIDDEN = 400;

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

export function readFocus(): string[] {
  return strings(readJson<unknown>(FOCUS));
}

export function writeFocus(keys: string[]): void {
  writeJson(FOCUS, keys);
}

/** A focus the profile has not accepted yet (offline, or the endpoint was not there). */
export function readPendingFocus(): string[] | null {
  const raw = readJson<unknown>(PENDING);
  return Array.isArray(raw) ? strings(raw) : null;
}

export function writePendingFocus(keys: string[] | null): void {
  if (keys === null) removeKey(PENDING);
  else writeJson(PENDING, keys);
}

export interface SavedItem {
  id: string;
  label: string;
  href: string;
}

export function readSaved(): SavedItem[] {
  const raw = readJson<unknown>(SAVED);
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (v): v is SavedItem =>
      !!v && typeof v === "object" && typeof (v as SavedItem).id === "string" && typeof (v as SavedItem).href === "string",
  );
}

export function toggleSaved(item: SavedItem): boolean {
  const saved = readSaved();
  const has = saved.some((s) => s.id === item.id);
  const next = has ? saved.filter((s) => s.id !== item.id) : [item, ...saved].slice(0, MAX_SAVED);
  writeJson(SAVED, next);
  return !has;
}

export function readHidden(): string[] {
  return strings(readJson<unknown>(HIDDEN));
}

export function writeHidden(ids: string[]): void {
  writeJson(HIDDEN, ids.slice(-MAX_HIDDEN));
}

/** Category key -> how many times the student asked for less of it. */
export function readLess(): Record<string, number> {
  const raw = readJson<unknown>(LESS);
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof v === "number" && v > 0) out[k] = Math.min(v, 9);
  }
  return out;
}

export function writeLess(less: Record<string, number>): void {
  writeJson(LESS, less);
}
