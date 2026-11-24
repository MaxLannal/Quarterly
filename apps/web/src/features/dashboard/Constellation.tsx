import { Chip } from "./parts";

/**
 * The interests as a compact, still cloud of chips (the orbiting version was removed at Max's
 * request, 2026-11-20). `center` is kept for callers; the student's name is not repeated here.
 */
export function Constellation({ items, onRemove }: { items: string[]; onRemove: (item: string) => void; center?: string }) {
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Interests">
      {items.map((item) => (
        <li key={item}>
          <Chip label={item} onRemove={() => onRemove(item)} />
        </li>
      ))}
    </ul>
  );
}
