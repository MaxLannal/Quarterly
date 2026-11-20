import type { ReactNode } from "react";

/**
 * Balanced columns: each item goes to the column that is shortest so far (by an estimated
 * height), in feed order. The rule only looks at earlier items, so loading the next page never
 * moves a card that is already on screen.
 */
export function Masonry<T extends { id: string }>({
  items,
  columns,
  estimate,
  render,
  itemClassName,
}: {
  items: T[];
  columns: number;
  estimate: (item: T) => number;
  render: (item: T, index: number) => ReactNode;
  itemClassName?: (item: T) => string;
}) {
  const cols: { item: T; index: number }[][] = Array.from({ length: Math.max(columns, 1) }, () => []);
  const heights = cols.map(() => 0);
  items.forEach((item, index) => {
    let target = 0;
    for (let c = 1; c < heights.length; c++) if (heights[c]! < heights[target]! - 24) target = c;
    cols[target]!.push({ item, index });
    heights[target] = (heights[target] ?? 0) + estimate(item);
  });
  return (
    <div className="grid items-start gap-5" style={{ gridTemplateColumns: `repeat(${cols.length}, minmax(0, 1fr))` }}>
      {cols.map((col, c) => (
        <div key={c} className="flex min-w-0 flex-col gap-5">
          {col.map(({ item, index }) => (
            <div key={item.id} className={`min-w-0 ${itemClassName?.(item) ?? ""}`}>
              {render(item, index)}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
