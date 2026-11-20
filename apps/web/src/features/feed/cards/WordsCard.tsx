import { useId, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { searchHref, type WordsItem } from "../api";
import { hash, rng } from "../art/rng";
import { useInView, useReducedMotion, useRegisterWords } from "../hooks";
import { AiNote } from "./parts";

const SIZE = ["", "text-[15px]", "text-[18px]", "text-[22px]", "text-[27px]", "text-[33px]"];
const TONE = ["", "text-muted", "text-body", "text-ink", "text-ink", "text-primary"];

/** A word cloud of a category's course titles; every word searches the catalog. */
export function WordsCard({ item, note }: { item: WordsItem; note?: string }) {
  const id = useId();
  const reduced = useReducedMotion();
  const [ref, inView] = useInView<HTMLElement>("100px");
  useRegisterWords(item.id, item.words.slice(0, 8).map((w) => w.text), inView && !reduced);
  const r = rng(hash(item.id));
  // A shuffled order so the big words do not all sit at the start.
  const words = [...item.words].map((w) => ({ w, k: r() })).sort((a, b) => a.k - b.k).map(({ w }) => w);
  return (
    <article
      ref={ref}
      aria-labelledby={id}
      data-paused={!inView}
      className="relative overflow-hidden rounded-xl border border-hairline bg-canvas-soft p-6"
    >
      <p className="text-caption-uppercase uppercase text-muted">In other words</p>
      <h3 id={id} className="mt-1 font-display text-[22px] font-light leading-tight text-ink">
        What {item.label} talks about
      </h3>
      <ul className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1" aria-label={`Words from ${item.label} course titles`}>
        {words.map((w, i) => {
          const style = { "--duration": `${4 + ((i * 7) % 5)}s`, "--delay": `${-((i * 0.37) % 4)}s` } as CSSProperties;
          return (
            <li key={w.text}>
              <Link
                to={searchHref(w.text)}
                className={cn(
                  "feed-bob inline-flex min-h-11 items-center rounded-sm px-0.5 font-display leading-none hover:text-primary hover:underline",
                  SIZE[w.weight],
                  TONE[w.weight],
                  w.weight >= 4 ? "font-normal" : "font-light italic",
                )}
                style={style}
                aria-label={`Search courses for ${w.text}`}
              >
                {w.text}
              </Link>
            </li>
          );
        })}
      </ul>
      {note && (
        <div className="mt-3">
          <AiNote note={note} />
        </div>
      )}
    </article>
  );
}
