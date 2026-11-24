import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { AskBar } from "@/features/home/AskBar";
import { CourseChapel } from "@/features/home/CourseChapel";
import { SceneSwitch, useScene } from "@/features/home/NightScene";
import { activePlan } from "@/features/planner/localPlans";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/** Short questions under the bar; each opens the Ask chatbot with it. */
const TRY = [
  "Quantum computing as a first-year?",
  "A Hum sequence for film lovers",
  "CS BA or BS?",
];

/** hero-band: the whole first screen is Rockefeller Chapel, drawn with the catalog's course titles
 * (CourseChapel); the title, the question bar and the pills sit on it, beside the chapel on wide
 * screens and under its spires on phones. The title is "The Best of UChicago, within your reach."
 * (docs/BEST-OF-UCHICAGO-PLAN.md), and the bar asks the Ask chatbot instead of searching. */
export default function HomePage() {
  const navigate = useNavigate();
  const sectionRef = useRef<HTMLElement>(null);
  const uiRef = useRef<HTMLDivElement>(null);
  const [scene, setScene] = useScene();
  const night = scene === "night";
  // Issue #16: a new student signs up first (the registration form sets up the plan's basics).
  const { data: session } = useSession();
  const [hasPlan] = useState(() => {
    try {
      return activePlan() !== null;
    } catch {
      return false;
    }
  });
  return (
    <section
      ref={sectionRef}
      aria-label="Quarterly"
      data-scene={scene}
      className={cn(
        "relative isolate flex h-[calc(100svh-100px)] min-h-[640px] overflow-hidden",
      )}
    >
      <CourseChapel sectionRef={sectionRef} uiRef={uiRef} night={night} />
      {/* Day or the snowy night (Max, 2026-11-20); remembered on this device. */}
      <div className="absolute right-3 top-3 z-10 sm:right-5 sm:top-5">
        <SceneSwitch scene={scene} onChange={setScene} />
      </div>
      <div className="mx-auto flex w-full max-w-[1880px] items-end px-4 pb-8 sm:px-8 sm:pb-14 chapel-side:items-center chapel-side:px-12 chapel-side:pb-0">
        <div
          ref={uiRef}
          className="flex w-full max-w-[34rem] flex-col items-start gap-5 chapel-side:gap-7"
        >
          <h1 className="home-title font-display text-ink">
            <span className="home-title-line home-title-lead">The Best of</span>{" "}
            <span className="home-title-line home-title-main">UChicago,</span>{" "}
            <span className="home-title-line home-title-reach">
              <em>within your reach.</em>
              <svg
                aria-hidden="true"
                className="home-title-swash"
                viewBox="0 0 320 24"
                preserveAspectRatio="none"
              >
                <path d="M4 15 C 70 4, 150 4, 214 11 S 300 20, 316 7" />
              </svg>
            </span>
          </h1>
          <AskBar />
          {/* On a phone the bar's typed-out placeholder shows the examples; the chapel keeps the room. */}
          <div className="-mt-1 hidden flex-wrap items-center gap-2 sm:flex" aria-label="Try a question">
            <span className="text-caption text-muted">Try</span>
            {TRY.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => navigate(`/ask?q=${encodeURIComponent(t)}`)}
                className="min-h-11 rounded-pill border border-hairline bg-canvas/85 px-3 text-caption text-body backdrop-blur-[2px] transition-colors hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                {t}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild>
              <Link to={session ? "/plan" : "/signup"}>Start planning</Link>
            </Button>
            <Button asChild variant="outline" className="bg-canvas">
              <Link to="/feed">Explore the feed</Link>
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
