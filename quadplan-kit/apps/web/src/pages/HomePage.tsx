import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Orb } from "@/components/ui/card";
import { SearchIcon } from "@/components/ui/icons";
import { controlClass } from "@/components/ui/input";
import { ChapelScene } from "@/features/home/ChapelScene";
import { cn } from "@/lib/utils";

/** hero-band: canvas, the wordmark as headline, search and one primary pill, one orb; beside it
 * (below it on narrow screens) the live ASCII chapel scene (FEEDBACK "ASCII Scene"). No subhead or
 * footnote: Richard cut them (FEEDBACK "Minor design changes" D1, 2026-11-16). */
export default function HomePage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    navigate(
      q.trim() ? `/courses?q=${encodeURIComponent(q.trim())}` : "/courses",
    );
  }
  return (
    <section className="relative isolate overflow-hidden">
      <Orb
        color="lake"
        className="-left-16 top-0 size-[320px] sm:left-0 sm:size-[480px] lg:-top-6 lg:left-[8%] lg:size-[560px]"
      />
      <div className="mx-auto grid w-full max-w-content items-center gap-10 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:px-8 lg:py-section">
        <div className="flex min-w-0 flex-col items-start gap-8">
          <h1 className="font-display text-[64px] font-normal leading-none tracking-[-1.92px] text-ink text-balance sm:text-display-hero">
            Quarterly
          </h1>
          <form
            role="search"
            onSubmit={submit}
            className="flex w-full max-w-xl flex-col gap-3 sm:flex-row"
            aria-label="Search courses and instructors"
          >
            <label htmlFor="home-search" className="sr-only">
              Search courses and instructors
            </label>
            <div className="relative min-w-0 flex-1">
              <SearchIcon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
              <input
                id="home-search"
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Course code or title"
                className={cn(controlClass, "rounded-pill pl-11")}
              />
            </div>
            <Button type="submit" variant="outline">
              Search
            </Button>
          </form>
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild>
              <Link to="/onboarding">Start planning</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/instructors">Browse reviews</Link>
            </Button>
            <Link
              to="/plan"
              className={cn(standaloneLinkClass, "px-2 text-button")}
            >
              Open my plan
            </Link>
          </div>
        </div>
        <ChapelScene />
      </div>
    </section>
  );
}
