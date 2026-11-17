/**
 * Forum dates are day-level only (SPEC "Anonymity inside the forum": "Autumn 2026" or
 * "3 weeks ago", never to the minute). The API sends a day; we show a relative phrase.
 */
export function relativeDay(day: string, today: Date = new Date()): string {
  const [y, mo, d] = day.split("-").map(Number);
  if (!y || !mo || !d) return day;
  const then = Date.UTC(y, mo - 1, d);
  const now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.round((now - then) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  if (days < 30) {
    const w = Math.floor(days / 7);
    return w === 1 ? "1 week ago" : `${w} weeks ago`;
  }
  if (days < 365) {
    const m = Math.floor(days / 30);
    return m === 1 ? "1 month ago" : `${m} months ago`;
  }
  const yrs = Math.floor(days / 365);
  return yrs === 1 ? "1 year ago" : `${yrs} years ago`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** URL path of a forum page and of a thread on it. */
export function pagePath(code: string, slug: string): string {
  return `/courses/${encodeURIComponent(code)}/i/${encodeURIComponent(slug)}`;
}

export function threadPath(code: string, slug: string, postId: number): string {
  return `${pagePath(code, slug)}/t/${postId}`;
}

/** Comments deeper than this are folded behind "Continue this thread" (SPEC: below depth 6). */
export const COLLAPSE_DEPTH = 6;
