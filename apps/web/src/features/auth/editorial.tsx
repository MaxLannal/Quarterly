import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import "./editorial.css";

export interface IndexEntry {
  id: string;
  label: string;
}

/**
 * An editorial reading page (docs/DESIGN.md "Dark glass"; About, Privacy, Account): a mono eyebrow,
 * a large display-serif title and a lede over a narrow reading column. With `index`, wide screens
 * get a sticky glass index of the page's sections beside the column (plain links to the section
 * ids; on narrow screens the index is not shown, the page reads straight down).
 */
export function EditorialPage({
  eyebrow,
  title,
  lede,
  index,
  children,
  className,
}: {
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
  index?: IndexEntry[];
  children: ReactNode;
  className?: string;
}) {
  return (
    <article className={cn("editorial", index && "editorial-indexed", className)}>
      <header className="editorial-head">
        <p className="mono-label text-primary">{eyebrow}</p>
        <h1 className="editorial-title">{title}</h1>
        {lede && <div className="editorial-lede">{lede}</div>}
      </header>
      {index && (
        <nav aria-label="On this page" className="editorial-index">
          <p aria-hidden="true" className="mono-label px-4 pb-2 text-muted">
            On this page
          </p>
          <ol>
            {index.map((entry, i) => (
              <li key={entry.id}>
                <a href={`#${entry.id}`}>
                  <span aria-hidden="true" className="editorial-index-n">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  {entry.label}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="editorial-body">{children}</div>
    </article>
  );
}

/** A numbered section of an editorial page: a mono number over a display-serif heading. */
export function EditorialSection({ id, n, title, children, className }: { id: string; n?: number; title: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className={cn("editorial-section", className)}>
      {n !== undefined && (
        <p aria-hidden="true" className="mono-label text-primary">
          {String(n).padStart(2, "0")}
        </p>
      )}
      <h2 id={`${id}-title`} className="editorial-h2">
        {title}
      </h2>
      {children}
    </section>
  );
}
