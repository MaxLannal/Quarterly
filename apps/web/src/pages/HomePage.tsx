import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { GlassFile, GlassFolder, type FolderTone } from "@/components/ui/folder";
import { HarperHall } from "@/features/home/HarperHall";
import { SceneSwitch, useScene } from "@/features/home/NightScene";
import { activePlan } from "@/features/planner/localPlans";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import "@/features/home/home.css";

/** The three folders under the hero: what each part of Quarterly holds (facts about the product only). */
const FOLDERS: { to: string; name: string; tone: FolderTone; files: string[]; cta: string }[] = [
  {
    to: "/plan",
    name: "Planner",
    tone: "ember",
    files: ["Quarters as folders, classes as files", "Checked against your program's rules", "Drag a class to another quarter"],
    cta: "Open the planner",
  },
  {
    to: "/courses",
    name: "Catalog",
    tone: "smoke",
    files: ["Every course, by code or title", "Programs and what they require", "Student ratings beside each course"],
    cta: "Browse the catalog",
  },
  {
    to: "/forum",
    name: "Forum",
    tone: "garnet",
    files: ["Reviews by course and instructor", "Questions with a first answer", "Anonymous by design"],
    cta: "Visit the forum",
  },
];

/**
 * The pointer tilts the picture a few degrees, like a pane of glass turned in the hand (writes two
 * CSS variables on the stage; the transform runs on the compositor). Off for touch and reduced motion.
 */
function useTilt(stageRef: React.RefObject<HTMLDivElement | null>, areaRef: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const stage = stageRef.current;
    const area = areaRef.current;
    if (!stage || !area) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce), (pointer: coarse)").matches) return;
    let frame = 0;
    let tx = 0;
    let ty = 0;
    const paint = () => {
      frame = 0;
      stage.style.setProperty("--tilt-x", tx.toFixed(3));
      stage.style.setProperty("--tilt-y", ty.toFixed(3));
    };
    const onMove = (e: PointerEvent) => {
      const r = area.getBoundingClientRect();
      tx = ((e.clientX - r.left) / r.width - 0.5) * 2;
      ty = ((e.clientY - r.top) / r.height - 0.5) * 2;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const onLeave = () => {
      tx = 0;
      ty = 0;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    area.addEventListener("pointermove", onMove, { passive: true });
    area.addEventListener("pointerleave", onLeave);
    return () => {
      area.removeEventListener("pointermove", onMove);
      area.removeEventListener("pointerleave", onLeave);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [stageRef, areaRef]);
}

/** hero-band: the title beside Harper Memorial Library's reading room drawn in light, on the night
 * itself (no pane); then the three folders. The title is "The Best of UChicago, within your
 * reach." (docs/BEST-OF-UCHICAGO-PLAN.md); docs/DESIGN.md "Dark glass" has the rest. */
export default function HomePage() {
  const sectionRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [scene, setScene] = useScene();
  useTilt(stageRef, sectionRef);
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
    <>
      <section ref={sectionRef} aria-label="Quarterly" data-scene={scene} className="home-hero relative isolate">
        <div className="mx-auto grid min-h-[calc(100svh-100px)] w-full max-w-[1760px] grid-cols-1 items-center gap-10 px-5 pb-12 pt-6 sm:px-8 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.3fr)] lg:gap-14 lg:px-14 lg:py-12">
          <div className="home-copy order-2 flex flex-col items-start gap-7 lg:order-1">
            <p className="home-rise mono-label text-on-night-soft" style={{ animationDelay: "40ms" }}>
              <span aria-hidden="true" className="mr-2 inline-block size-1.5 translate-y-[-1px] rounded-pill bg-primary shadow-[0_0_10px_2px_rgb(255_92_112/0.7)]" />
              Plan · Catalog · Forum
            </p>
            <h1 className="home-title font-display text-ink">
              <span className="home-title-line home-title-lead">The Best of</span>{" "}
              <span className="home-title-line home-title-main">UChicago,</span>{" "}
              <span className="home-title-line home-title-reach">
                <em>within your reach.</em>
                <svg aria-hidden="true" className="home-title-swash" viewBox="0 0 320 24" preserveAspectRatio="none">
                  <path d="M4 15 C 70 4, 150 4, 214 11 S 300 20, 316 7" />
                </svg>
              </span>
            </h1>
            <p className="home-rise max-w-[30rem] text-body-md text-body" style={{ animationDelay: "380ms" }}>
              Every course of the College, four years of quarters, and what students really think, kept in one quiet reading room.
            </p>
            <div className="home-rise flex flex-wrap items-center gap-3" style={{ animationDelay: "480ms" }}>
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
            {/* Sunlight or lamplight in the reading room (Max, 2026-11-20); remembered on this device. */}
            <div className="home-rise" style={{ animationDelay: "560ms" }}>
              <SceneSwitch scene={scene} onChange={setScene} />
            </div>
          </div>

          <div ref={stageRef} className="home-stage order-1 lg:order-2">
            <figure className="home-panel">
              <div className="home-panel-frame">
                <HarperHall scene={scene} />
              </div>
              {/* Floating glass chips, at different depths over the picture (decorative). */}
              <div aria-hidden="true" className="home-chip home-chip-a">
                <span className="mono-label text-muted">Reading room</span>
                <span className="text-body-sm font-medium text-ink">Harper Library</span>
              </div>
              <div aria-hidden="true" className="home-chip home-chip-b">
                <span className="flex size-8 items-center justify-center rounded-pill bg-primary/20 text-primary shadow-[inset_0_0_0_1px_rgb(255_92_112/0.4)]">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12.5l4.5 4.5L19 7.5" />
                  </svg>
                </span>
                <span className="flex flex-col">
                  <span className="mono-label text-muted">Verified</span>
                  <span className="text-body-sm font-medium text-ink">Every plan is checked</span>
                </span>
              </div>
              <div aria-hidden="true" className="home-chip home-chip-c">
                <span className="mono-label text-muted">Autumn</span>
                <span className="flex items-center gap-2 text-body-sm font-medium text-ink">
                  <span className="home-chip-file" />
                  <span className="home-chip-file" />
                  <span className="home-chip-file" />
                  3 classes
                </span>
              </div>
              <figcaption className="mono-label mt-4 text-on-night-muted">Harper Memorial Library — the reading room</figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section aria-labelledby="home-folders-title" className="mx-auto w-full max-w-[1560px] px-5 pb-20 pt-6 sm:px-8 lg:px-14 lg:pb-28">
        <div className="mb-10 flex flex-col gap-3 lg:mb-14">
          <p className="mono-label text-on-night-muted">What's inside</p>
          <h2 id="home-folders-title" className="max-w-[18ch] font-display text-display-md text-ink sm:text-display-lg">
            Four years, kept <em>in folders.</em>
          </h2>
        </div>
        <ul className="grid grid-cols-1 gap-8 md:grid-cols-3 md:gap-6 xl:gap-10">
          {FOLDERS.map((f, i) => (
            <li key={f.to} className="home-folder" style={{ animationDelay: `${120 * i}ms` }}>
              <GlassFolder
                tone={f.tone}
                tabRatio={0.46}
                tab={
                  <Link
                    to={f.to}
                    className="rounded-xs text-title-sm text-ink after:absolute after:inset-0 after:z-[4] after:rounded-[22px] after:content-['']"
                  >
                    {f.name}
                  </Link>
                }
                aside={<span className="mono-label text-muted">0{i + 1}</span>}
                pocket={
                  <span className="mono-label flex items-center gap-2 text-ink">
                    {f.cta}
                    <span aria-hidden="true" className="text-primary transition-transform duration-300 group-hover/folder:translate-x-1">
                      →
                    </span>
                  </span>
                }
                className="group/folder min-h-[300px] hover:-translate-y-1"
              >
                {f.files.map((line, j) => (
                  <GlassFile key={line} className="flex items-baseline gap-3 px-4 py-3">
                    <span className="mono-label text-muted">{String(j + 1).padStart(2, "0")}</span>
                    <span className="text-body-sm text-body-strong">{line}</span>
                  </GlassFile>
                ))}
              </GlassFolder>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
