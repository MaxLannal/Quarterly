import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { LoadingState, PageContainer } from "@/components/layout/page";
import { Button, buttonVariants } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { Notice } from "@/components/ui/misc";
import { useAuthLinks } from "@/features/auth/next";
import { errorText, useProfile, type Profile, type Topic, type TurnEvent } from "@/features/dashboard/api";
import "@/features/dashboard/dashboard.css";
import { GuideCard } from "@/features/dashboard/GuideCard";
import { GuideOverlay } from "@/features/dashboard/GuideOverlay";
import { IdentityFields, memberLine } from "@/features/dashboard/IdentityCard";
import { CompletenessRing, GuideMark } from "@/features/dashboard/parts";
import { CareerCard, ConstraintsCard, HorizonsCard, HumanitiesCard, InterestsCard, PortraitHeader, ResearchCard } from "@/features/dashboard/Portrait";
import { useGuide } from "@/features/dashboard/useGuide";
import { WhatsNew } from "@/features/dashboard/WhatsNew";
import { useSession } from "@/lib/session";

/** The dashboard's frame: the full width of the page sheet, panels packed close together. */
const GRID = "mx-auto grid w-full max-w-[1760px] grid-cols-1 gap-3 p-3 sm:p-4 md:grid-cols-6 xl:grid-cols-12";

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
 * wants from UChicago and a guide who remembers them. "Your routes" and "At a glance" went in
 * issue #15: the planner makes every plan proposal.
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
    <div className={GRID}>
      <section className="flex flex-col justify-center gap-4 rounded-[22px] border border-hairline bg-surface-card p-5 sm:p-7 md:col-span-6 xl:col-span-8">
        <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-primary">Your Quarterly</p>
        <h1 className="font-display text-[40px] font-extrabold leading-[1.02] tracking-[-1.4px] text-ink sm:text-[52px]">
          A place that <em>remembers</em> you.
        </h1>
        <p className="max-w-[40rem] text-body-md text-body">
          A portrait of what you want from UChicago, and a guide who remembers.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link to={links.signup} className={buttonVariants()}>
            Sign up
          </Link>
          <Link to={links.login} className={buttonVariants({ variant: "outline" })}>
            Log in
          </Link>
        </div>
      </section>
      <section aria-label="Your guide, for example" className="rounded-[22px] bg-surface-dark p-5 text-on-dark md:col-span-6 xl:col-span-4">
        <p className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-[0.08em] text-on-dark-soft">
          <GuideMark size={14} className="text-primary" /> Your guide
        </p>
        <p className="mt-3 font-serif text-[20px] font-light leading-[1.35]">
          “Last time you told me you love Greek tragedy and that you're heading toward quantum computing. Want to pick up where we left off?”
        </p>
      </section>
      {[
        ["Your portrait", "Interests, a humanities compass, research questions and the fields you're heading toward, in your own words."],
        ["A guide who remembers", "Ten minutes of good questions, one at a time. Next time, it picks up where you left off."],
      ].map(([title, text]) => (
        <section key={title} className="rounded-[22px] border border-hairline bg-surface-card p-4 sm:p-5 md:col-span-3 xl:col-span-6">
          <h2 className="font-display text-[21px] font-bold tracking-[-0.02em] text-ink">{title}</h2>
          <p className="mt-1.5 text-body-sm text-body">{text}</p>
        </section>
      ))}
      <div className="md:col-span-6 xl:col-span-12">
        <Preview />
      </div>
    </div>
  );
}

/** An illustration of a filled dashboard, blurred: what logging in opens. */
function Preview() {
  return (
    <div aria-hidden="true" className="relative overflow-hidden rounded-[22px] border border-hairline bg-canvas-soft p-4 sm:p-6">
      <div className="dash-preview grid gap-3 md:grid-cols-[1.3fr_1fr]">
        <div className="rounded-xxl bg-surface-dark p-6 text-on-dark">
          <p className="text-caption-uppercase uppercase text-on-dark-soft">Your guide</p>
          <p className="mt-3 font-serif text-[24px] font-light leading-snug">Welcome back. Last time you told me you love Greek tragedy and that you're heading toward quantum computing. Want to pick up where we left off?</p>
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

  const openGuide = useCallback(
    (options?: { seed?: TurnEvent | null; message?: string }) => {
      setOpen(true);
      guide.begin(options);
    },
    [guide],
  );
  const ask = useCallback((topic: Topic) => openGuide({ message: ASK_ABOUT[topic] }), [openGuide]);

  const year = profile.class_year;
  return (
    <>
      <div className={GRID}>
        {/* Top left: who the student is, and what to do next. */}
        <section aria-labelledby="dash-name" className="flex flex-col gap-4 rounded-[22px] border border-hairline bg-surface-card p-4 sm:p-5 md:col-span-6 xl:col-span-8">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <Avatar name={profile.username} className="size-14 shrink-0 bg-primary-wash text-title-md text-primary" />
              <div className="min-w-0">
                <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-primary">Your Quarterly</p>
                <h1 id="dash-name" className="font-display text-[30px] font-extrabold leading-[1.05] tracking-[-0.9px] text-ink sm:text-[38px]">
                  {profile.username}, <em>{year ? `Class of ${year}` : "welcome"}</em>.
                </h1>
                <p className="truncate text-body-sm text-body">
                  {profile.email} · {memberLine(profile)}
                </p>
              </div>
            </div>
            <CompletenessRing value={profile.completeness} size={56} />
          </div>
          <div className="rounded-[16px] bg-canvas-soft p-3 sm:p-4">
            <PortraitHeader profile={profile} onAsk={ask} />
          </div>
          <IdentityFields profile={profile} />
          <div className="mt-auto flex flex-wrap items-center gap-2">
            <Button onClick={() => openGuide()}>
              <GuideMark size={14} /> Talk with your guide
            </Button>
          </div>
        </section>

        {/* Top right: the guide. */}
        <div className="md:col-span-6 xl:col-span-4">
          <GuideCard profile={profile} onOpen={openGuide} paused={open} />
        </div>

        <div className="md:col-span-3 xl:col-span-4">
          <InterestsCard profile={profile} onAsk={ask} />
        </div>
        <div className="md:col-span-3 xl:col-span-4">
          <ResearchCard profile={profile} onAsk={ask} />
        </div>
        <div className="md:col-span-6 xl:col-span-4">
          <WhatsNew />
        </div>

        <div className="md:col-span-6 xl:col-span-6">
          <HumanitiesCard profile={profile} onAsk={ask} />
        </div>
        <div className="md:col-span-3 xl:col-span-3">
          <CareerCard profile={profile} onAsk={ask} />
        </div>
        <div className="md:col-span-3 xl:col-span-3">
          <HorizonsCard profile={profile} onAsk={ask} />
        </div>

        <div className="md:col-span-6 xl:col-span-12">
          <ConstraintsCard profile={profile} onAsk={ask} />
        </div>
      </div>

      <GuideOverlay
        open={open}
        onClose={() => {
          setOpen(false);
          guide.stop();
        }}
        guide={guide}
        profile={profile}
      />
    </>
  );
}
