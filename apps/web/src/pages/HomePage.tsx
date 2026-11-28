import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { ArrowIcon, BookIcon, ChatIcon, FolderIcon } from "@/components/ui/icons";
import { HarperHall } from "@/features/home/HarperHall";
import { SceneSwitch, useScene } from "@/features/home/NightScene";
import { activePlan } from "@/features/planner/localPlans";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/** The three parts of Quarterly, as cards (facts about the product only). */
const PARTS: { to: string; name: string; text: string; icon: (p: { size?: number }) => ReactNode }[] = [
  { to: "/plan", name: "Planner", text: "Quarters as folders, classes as files, checked against your program's rules.", icon: FolderIcon },
  { to: "/courses", name: "Catalog", text: "Every course by code or title, the programs, and student ratings beside each course.", icon: BookIcon },
  { to: "/forum", name: "Forum", text: "Anonymous reviews by course and instructor, and questions with a first answer.", icon: ChatIcon },
];

/** Home ("Simple light", docs/DESIGN.md): the title and buttons, Harper Memorial Library's reading
 * room in a white card, and the three parts of Quarterly. The title is "The Best of UChicago,
 * within your reach." (docs/BEST-OF-UCHICAGO-PLAN.md). */
export default function HomePage() {
  const [scene, setScene] = useScene();
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
    <section aria-label="Quarterly" data-scene={scene} className="mx-auto w-full max-w-content px-4 pb-16 pt-6 sm:px-6 sm:pt-8 lg:px-8">
      <div className="flex flex-col gap-4">
        <h1 className="home-title text-display-md text-ink sm:text-display-xl lg:text-display-mega">
          The Best of UChicago, <em>within your reach.</em>
        </h1>
        <p className="max-w-[36rem] text-body-md text-body">
          Every course of the College, four years of quarters, and what students really think, in one place.
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Button asChild>
            <Link to={session ? "/plan" : "/signup"}>Start planning</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/courses">Explore the catalog</Link>
          </Button>
          {/* D11 H-3: only when there is a plan to open. */}
          {hasPlan && (
            <Link to="/plan" className={cn(standaloneLinkClass, "px-2 text-button")}>
              Open my plan
            </Link>
          )}
        </div>
      </div>

      <figure className="mt-10 overflow-hidden rounded-xxl border border-hairline bg-canvas">
        <div className="relative aspect-[4/3] sm:aspect-[16/9] lg:aspect-[21/9]">
          <HarperHall scene={scene} />
        </div>
        <figcaption className="flex flex-wrap items-center justify-between gap-3 border-t border-hairline px-5 py-3">
          <span className="text-caption text-muted">Harper Memorial Library, the reading room</span>
          {/* Sunlight or lamplight (Max, 2026-11-20); remembered on this device. */}
          <SceneSwitch scene={scene} onChange={setScene} />
        </figcaption>
      </figure>

      <ul aria-label="What's inside" className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        {PARTS.map((part) => {
          const Icon = part.icon;
          return (
            <li key={part.to} className="group relative flex flex-col gap-3 rounded-xl border border-hairline bg-canvas p-5 transition-[border-color,box-shadow] duration-200 hover:border-hairline-strong hover:shadow-hover">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-title-md">
                  <Link to={part.to} className="rounded-xs after:absolute after:inset-0 after:rounded-xl after:content-['']">
                    {part.name}
                  </Link>
                </h2>
                <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-lg border border-hairline text-ink">
                  <Icon size={19} />
                </span>
              </div>
              <p className="text-body-sm text-muted">{part.text}</p>
              <span aria-hidden="true" className="mt-auto inline-flex items-center gap-1.5 text-caption font-semibold text-ink">
                Open <ArrowIcon size={14} className="transition-transform duration-200 group-hover:translate-x-0.5" />
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
