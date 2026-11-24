/**
 * Composer drafts, kept in this browser only (localStorage), one per context ("new question",
 * "answer on thread 12", "reply to reply 40", "edit reply 40"). Cleared when the text is posted.
 * Day-level dates only; drafts older than 30 days are dropped.
 */
import { readJson, removeKey, writeJson } from "@/lib/storage";

const PREFIX = "quarterly.commons.draft.";
const MAX_DAYS = 30;

interface Stored<T> {
  value: T;
  day: string;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function fresh(day: string): boolean {
  const then = Date.parse(`${day}T00:00:00Z`);
  return Number.isFinite(then) && Date.now() - then < MAX_DAYS * 86_400_000;
}

export function readDraft<T = string>(key: string): T | null {
  const stored = readJson<Stored<T>>(PREFIX + key);
  if (!stored || typeof stored !== "object" || !("value" in stored)) return null;
  if (!fresh(stored.day)) {
    removeKey(PREFIX + key);
    return null;
  }
  return stored.value;
}

/** Returns false when the browser would not store it. */
export function writeDraft<T>(key: string, value: T): boolean {
  return writeJson(PREFIX + key, { value, day: today() } satisfies Stored<T>);
}

export function clearDraft(key: string): void {
  removeKey(PREFIX + key);
}
