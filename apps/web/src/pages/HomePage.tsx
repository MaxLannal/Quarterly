import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { SearchIcon } from "@/components/ui/icons";
import { controlClass } from "@/components/ui/input";
import { CourseChapel } from "@/features/home/CourseChapel";
import { activePlan } from "@/features/planner/localPlans";
import { cn } from "@/lib/utils";

/** hero-band: the whole first screen is Rockefeller Chapel, drawn with the catalog's course titles
 * (CourseChapel); the wordmark, search and the two pills sit on it, beside the chapel on wide
 * screens and under its spires on phones. No subhead or footnote: Richard cut them (FEEDBACK
 * "Minor design changes" D1, 2026-11-16). The chapel is the page's atmosphere, so no orb. */
export default function HomePage() {
  const navigate = useNavigate();
  const sectionRef = useRef<HTMLElement>(null);
  const uiRef = useRef<HTMLDivElement>(null);
  const [q, setQ] = useState("");
  const [hasPlan] = useState(() => {
    try {
      return activePlan() !== null;
    } catch {
      return false;
    }
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    navigate(
      q.trim() ? `/courses?q=${encodeURIComponent(q.trim())}` : "/courses",
    );
  }
  return (
    <section
      ref={sectionRef}
      aria-label="Quarterly"
      className="relative isolate flex h-[calc(100svh-65px)] min-h-[560px] overflow-hidden"
    >
      <CourseChapel sectionRef={sectionRef} uiRef={uiRef} />
      <div className="mx-auto flex w-full max-w-[1600px] items-end px-4 pb-10 sm:px-8 sm:pb-14 chapel-side:items-center chapel-side:px-12 chapel-side:pb-0">
        <div
          ref={uiRef}
          className="flex w-full max-w-[26rem] flex-col items-start gap-6 chapel-side:gap-8"
        >
          <h1 className="font-display text-[64px] font-normal leading-none tracking-[-1.92px] text-ink sm:text-display-hero">
            Quarterly
          </h1>
          <form
            role="search"
            onSubmit={submit}
            className="flex w-full flex-row gap-3"
            aria-label="Search courses"
          >
            <label htmlFor="home-search" className="sr-only">
              Search courses
            </label>
            <div className="relative min-w-0 flex-1">
              <SearchIcon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
              <input
                id="home-search"
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Code or title, e.g. CMSC 14100"
                className={cn(controlClass, "rounded-pill pl-11")}
              />
            </div>
            <Button type="submit" variant="outline" className="bg-canvas">
              Search
            </Button>
          </form>
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild>
              <Link to="/onboarding">Start planning</Link>
            </Button>
            <Button asChild variant="outline" className="bg-canvas">
              <Link to="/instructors">Browse reviews</Link>
            </Button>
            {/* D11 H-3: only when there is a plan to open. */}
            {hasPlan && (
              <Link
                to="/plan"
                className={cn(standaloneLinkClass, "px-2 text-button")}
              >
                Open my plan
              </Link>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
