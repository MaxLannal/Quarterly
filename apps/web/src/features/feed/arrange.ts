/** Pure helpers that arrange the loaded pages on screen (tested in arrange.test.ts). */
import type { FeedItem, FeedPage } from "./api";

export function categoryOf(item: FeedItem): string | null {
  return "category" in item ? item.category.key : null;
}

/**
 * The items of the loaded pages, in order, without repeats or hidden items. "Show less like
 * this" moves a category's courses to the end of their page (once) and drops them (three times
 * or more), so a page keeps its other cards in place.
 */
export function arrange(pages: FeedPage[], hidden: ReadonlySet<string>, less: Readonly<Record<string, number>>): FeedItem[] {
  const seen = new Set<string>();
  const out: FeedItem[] = [];
  for (const page of pages) {
    const keep: FeedItem[] = [];
    const later: FeedItem[] = [];
    for (const item of page.items) {
      if (seen.has(item.id) || hidden.has(item.id)) continue;
      seen.add(item.id);
      const cat = item.kind === "course" ? categoryOf(item) : null;
      const n = cat ? (less[cat] ?? 0) : 0;
      if (n >= 3) continue;
      (n >= 1 ? later : keep).push(item);
    }
    out.push(...keep, ...later);
  }
  return out;
}

/** A rough height for the balanced columns (px at a 380px column). */
export function estimateHeight(item: FeedItem): number {
  switch (item.kind) {
    case "course":
      return 560 + item.books.length * 62 + (item.stats ? 30 : 0);
    case "comment":
      return 150 + item.snippet.length * 0.75;
    case "book":
      return 420;
    case "words":
      return 260 + item.words.length * 7;
    case "program":
      return 250;
    case "question":
      return 260;
  }
}

/** The ids of one page that the AI curator gets (at most 12). */
export function noteIds(page: FeedPage): string[] {
  return page.items.map((i) => i.id).slice(0, 12);
}

/** Course titles for the ticker: the loaded courses, at most `n`. */
export function tickerCourses(items: FeedItem[], n = 28): { code: string; title: string }[] {
  const out: { code: string; title: string }[] = [];
  for (const item of items) {
    if (item.kind === "course") out.push({ code: item.code, title: item.title });
    if (out.length >= n) break;
  }
  return out;
}
