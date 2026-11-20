import { useCallback, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { TypeHero } from "@/components/brand/TypeHero";
import { LoadingState, PageContainer } from "@/components/layout/page";
import { Button, buttonVariants } from "@/components/ui/button";
import { Notice } from "@/components/ui/misc";
import { useAuthLinks } from "@/features/auth/next";
import { errorText, useProfile, type Profile, type Topic, type TurnEvent } from "@/features/dashboard/api";
import "@/features/dashboard/dashboard.css";
import { GuideCard } from "@/features/dashboard/GuideCard";
import { GuideOverlay } from "@/features/dashboard/GuideOverlay";
import { IdentityCard } from "@/features/dashboard/IdentityCard";
import { ownWords } from "@/features/dashboard/logic";
import { CompletenessRing, GuideMark } from "@/features/dashboard/parts";
import { CareerCard, ConstraintsCard, HorizonsCard, HumanitiesCard, InterestsCard, PortraitHeader, ResearchCard } from "@/features/dashboard/Portrait";
import { RoutesSection, type RoutesHandle } from "@/features/dashboard/Routes";
import { useGuide } from "@/features/dashboard/useGuide";
import { WhatsNew } from "@/features/dashboard/WhatsNew";
import { useSession } from "@/lib/session";

const ORBIT_LABEL = "Rings of real course titles orbiting a maroon sun";

/** What the guide is asked when a section invites it ("Ask me about this"). */
const ASK_ABOUT: Record<Topic, string> = {
  class_year: "Can we talk about my class year?",
  interests: "Can we talk about my interests?",
  humanities: "Can we talk about the humanities?",
  research: "Can we talk about research?",
  career: "Can we talk about my career plans?",
  future: "Can we talk about the future fields I'm heading toward?",
  constraints: "Can we talk about my workload?",
  wrapup: "Can we talk about my portrait?",
};

/**
 * The personal dashboard (`/me`, docs/BEST-OF-UCHICAGO-PLAN.md): a portrait of what the student
 * wants from UChicago, a guide who remembers them, and routes they can choose or keep open.
 */
export default function DashboardPage() {
  const session = useSession();
  if (session.isLoading) {
    return (
      <PageContainer>
        <LoadingState label="Opening your Quarterly" />
      </PageContainer>
    );
  }
  return session.data ? <Dashboard /> : <LoggedOut />;
}

function LoggedOut() {
  const links = useAuthLinks();
  return (
    <>
      <TypeHero
        shape="orbit"
        label={ORBIT_LABEL}
        words={["Greek tragedy", "quantum computing", "film", "philosophy of mind", "economics"]}
        kicker="Your Quarterly"
        title={
          <>
            A place that <em>remembers</em> you.
          </>
        }
        subline="Your Quarterly: a portrait of what you want from UChicago, a guide who remembers, and routes you can keep open."
      >
        <div className="flex flex-wrap gap-3">
          <Link to={links.signup} className={buttonVariants()}>
            Sign up
          </Link>
          <Link to={links.login} className={buttonVariants({ variant: "outline" })}>
            Log in
          </Link>
        </div>
      </TypeHero>
      <PageContainer>
        <div className="grid gap-6 lg:grid-cols-3">
          {[
            ["Your portrait", "Interests in orbit, a humanities compass, research questions and the horizons you're heading toward, in your own words."],
            ["A guide who remembers", "Ten minutes of good questions, one at a time. Next time, it picks up where you left off."],
            ["Routes, kept open", "Three different four-year routes drafted from your portrait. Choose one, or keep them all open."],
          ].map(([title, text]) => (
            <div key={title} className="rounded-xxl border border-hairline bg-surface-card p-6">
              <h2 className="font-display text-display-sm text-ink">{title}</h2>
              <p className="mt-2 text-body-sm text-body">{text}</p>
            </div>
          ))}
        </div>
        <Preview />
      </PageContainer>
    </>
  );
}

/** An illustration of a filled dashboard, blurred: what logging in opens. */
function Preview() {
  return (
    <div aria-hidden="true" className="relative mt-10 overflow-hidden rounded-xxl border border-hairline bg-canvas-soft p-6 sm:p-10">
      <div className="dash-preview grid gap-6 md:grid-cols-[1.3fr_1fr]">
        <div className="rounded-xxl bg-surface-dark p-6 text-on-dark">
          <p className="text-caption-uppercase uppercase text-on-dark-soft">Your guide</p>
          <p className="mt-3 font-serif text-[24px] font-light leading-snug">Welcome back. Last time you told me you love Greek tragedy and that you're heading toward quantum computing. Want to draft a few routes?</p>
        </div>
        <div className="rounded-xxl border border-hairline bg-surface-card p-6">
          <p className="font-display text-display-sm text-ink">“A physicist with a poet's ear”</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {["Physics", "Greek tragedy", "Film", "Quantum computing", "Poetry"].map((w) => (
              <span key={w} className="rounded-pill border border-hairline-strong px-3 py-1 text-body-sm text-ink">
                {w}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-xxl border border-hairline bg-surface-card p-6 md:col-span-2">
          <p className="font-display text-display-sm text-ink">Your routes</p>
          <div className="mt-4 grid grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((y) => (
              <div key={y} className="flex flex-col gap-2 rounded-xl bg-canvas-soft p-3">
                <span className="text-caption-uppercase uppercase text-muted">Year {y}</span>
                {[0, 1, 2].map((i) => (
                  <span key={i} className="h-8 rounded-lg border border-hairline bg-surface-card" style={{ boxShadow: `inset 3px 0 0 var(--color-${["primary", "data-1", "data-5"][i]})` }} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-[radial-gradient(ellipse_at_center,color-mix(in_srgb,var(--color-canvas)_80%,transparent)_0%,transparent_70%)]">
        <p className="rounded-pill bg-surface-card px-5 py-2.5 text-body-sm text-ink shadow-overlay">Log in to open yours</p>
      </div>
    </div>
  );
}

function Dashboard() {
  const profile = useProfile(true);
  if (profile.isLoading) {
    return (
      <PageContainer>
        <LoadingState label="Opening your Quarterly" lines={4} />
      </PageContainer>
    );
  }
  if (profile.error || !profile.data) {
    return (
      <PageContainer>
        <Notice tone="error" role="alert">
          {errorText(profile.error)}{" "}
          <button type="button" className="underline underline-offset-2" onClick={() => void profile.refetch()}>
            Try again
          </button>
        </Notice>
      </PageContainer>
    );
  }
  return <DashboardBody profile={profile.data} />;
}

function DashboardBody({ profile }: { profile: Profile }) {
  const guide = useGuide();
  const [open, setOpen] = useState(false);
  const routes = useRef<RoutesHandle>(null);

  const openGuide = useCallback(
    (options?: { seed?: TurnEvent | null; message?: string }) => {
      setOpen(true);
      guide.begin(options);
    },
    [guide],
  );
  const ask = useCallback((topic: Topic) => openGuide({ message: ASK_ABOUT[topic] }), [openGuide]);
  const draftRoutes = useCallback(() => {
    setOpen(false);
    guide.stop();
    window.setTimeout(() => routes.current?.draft(), 60);
  }, [guide]);

  const year = profile.class_year;
  return (
    <>
      <TypeHero
        shape="orbit"
        label={ORBIT_LABEL}
        words={ownWords(profile)}
        kicker="Your Quarterly"
        title={
          <>
            {profile.username}, <em>{year ? `Class of ${year}` : "welcome"}</em>.
          </>
        }
        subline={profile.portrait.headline || "Talk with your guide: a few good questions, and this page starts to look like you."}
      >
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => openGuide()}>
            <GuideMark size={14} /> Talk with your guide
          </Button>
          <Button variant="outline" onClick={draftRoutes}>
            Draft my routes
          </Button>
        </div>
        <CompletenessRing value={profile.completeness} />
      </TypeHero>

      <PageContainer className="flex flex-col gap-6 pt-8 sm:gap-8 sm:pt-10">
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-8">
            <GuideCard profile={profile} onOpen={openGuide} onDraftRoutes={draftRoutes} paused={open} />
          </div>
          <div className="lg:col-span-4">
            <IdentityCard profile={profile} />
          </div>
        </div>

        <section aria-labelledby="portrait-title" className="flex flex-col gap-4 pt-6 sm:pt-10">
          <p className="flex items-center gap-2 text-caption-uppercase uppercase text-primary">
            <span aria-hidden="true" className="inline-block h-px w-6 bg-primary" /> Your portrait
          </p>
          <h2 id="portrait-title" className="sr-only">
            Your portrait
          </h2>
          <PortraitHeader profile={profile} onAsk={ask} />
        </section>

        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <InterestsCard profile={profile} onAsk={ask} />
          </div>
          <div className="flex flex-col gap-6 lg:col-span-5">
            <ResearchCard profile={profile} onAsk={ask} />
            <WhatsNew />
          </div>
        </div>
        <HumanitiesCard profile={profile} onAsk={ask} />
        <HorizonsCard profile={profile} onAsk={ask} />
        <div className="grid gap-6 lg:grid-cols-2">
          <CareerCard profile={profile} onAsk={ask} />
          <ConstraintsCard profile={profile} onAsk={ask} />
        </div>

        <div className="pt-8">
          <RoutesSection ref={routes} profile={profile} />
        </div>
      </PageContainer>

      <GuideOverlay
        open={open}
        onClose={() => {
          setOpen(false);
          guide.stop();
        }}
        guide={guide}
        profile={profile}
        onDraftRoutes={draftRoutes}
      />
    </>
  );
}
