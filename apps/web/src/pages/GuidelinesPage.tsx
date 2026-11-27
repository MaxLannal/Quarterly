import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { inlineLinkClass, PageContainer, PageHeader } from "@/components/layout/page";
import { Kicker } from "@/features/courses/Glass";
import { COMMUNITY_RULES } from "@/features/forum/rules";

/** A glass panel with a mono kicker over a serif heading. */
function Panel({ id, kicker, title, children }: { id: string; kicker: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="qg-tile flex min-w-0 flex-col gap-4 p-7 sm:p-8">
      <Kicker>{kicker}</Kicker>
      <h2 id={`${id}-heading`} className="font-display text-display-sm text-ink">
        {title}
      </h2>
      <div className="text-body-sm text-body sm:text-body-md">{children}</div>
    </section>
  );
}

/**
 * SPEC "Moderation and community rules" and "Anonymity inside the forum", in plain words.
 * Dark glass: the rules are numbered glass tiles with lit serif numerals; how moderation works,
 * what others see and the note on instructors are three panels beneath.
 */
export default function GuidelinesPage() {
  return (
    <PageContainer as="article" className="max-w-[1240px] sm:pt-14">
      <PageHeader
        eyebrow="The forum // community"
        title="Community guidelines"
        size="xl"
        description="The forum is for honest, useful notes about courses and teaching. These rules keep it fair to students and instructors."
      />
      <div className="mt-6 flex flex-col gap-14 text-body-md text-body">
        <section id="rules" aria-labelledby="rules-heading">
          <div className="mb-6 flex flex-col gap-2 border-b border-hairline pb-4">
            <Kicker>01 <span aria-hidden="true" className="text-muted-soft">//</span> Before you post</Kicker>
            <h2 id="rules-heading" className="font-display text-display-sm text-ink sm:text-display-md">
              The rules
            </h2>
          </div>
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {COMMUNITY_RULES.map((rule, i) => (
              <li key={rule} className="qg-tile qg-rise flex gap-4 p-6" style={{ ["--i" as string]: i }}>
                <span aria-hidden="true" className="qg-numeral w-8 shrink-0 text-[40px] text-primary">
                  {i + 1}
                </span>
                <span className="pt-1 text-body-sm text-ink sm:text-body-md">{rule}</span>
              </li>
            ))}
          </ol>
          <p className="mt-6 max-w-reading border-l border-primary/60 pl-5 font-serif text-[19px] italic leading-[1.55] text-body">
            Criticism of how a course is taught is welcome. Comments about an instructor&apos;s appearance, health, family or private
            life are not.
          </p>
        </section>

        <div className="grid gap-4 lg:grid-cols-3">
          <Panel id="moderation" kicker="02 // Reports" title="How moderation works">
            <ul className="flex list-disc flex-col gap-2 pl-5 marker:text-primary">
              <li>Email addresses and phone numbers are removed from every post before anyone reads it.</li>
              <li>Posts and comments appear as soon as you submit them. Nothing reads them first.</li>
              <li>Anyone can report a post or comment. Moderators read every report and take down what breaks these guidelines.</li>
              <li>
                When a moderator removes a post, they may also suspend its author from posting, commenting and voting for a while. That is
                always a person&apos;s decision, never automatic. A suspended account can still log in and read.
              </li>
            </ul>
          </Panel>

          <Panel id="anonymity" kicker="03 // Anonymity" title="What others see">
            <ul className="flex list-disc flex-col gap-2 pl-5 marker:text-primary">
              <li>
                On each course and instructor page you get a random two-word name, such as &ldquo;Quiet Heron&rdquo;. It stays the same on
                that page and is different on every other page, so readers cannot connect your posts across pages.
              </li>
              <li>Dates are shown as &ldquo;3 weeks ago&rdquo; or a term, never to the minute.</li>
              <li>There are no profiles, follower counts or karma totals.</li>
              <li>
                What we store, and who could connect a post to you, is explained on the{" "}
                <Link to="/privacy" className={inlineLinkClass}>
                  privacy page
                </Link>
                .
              </li>
            </ul>
          </Panel>

          <Panel id="instructors" kicker="04 // Teaching" title="Instructors">
            <p>
              Instructors cannot reply on the forum for now. Report anything that crosses a line, and take concerns about misconduct to
              the University instead of posting them.
            </p>
          </Panel>
        </div>
      </div>
    </PageContainer>
  );
}
