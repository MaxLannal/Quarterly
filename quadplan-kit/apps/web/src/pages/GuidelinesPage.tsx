import { Link } from "react-router-dom";
import { inlineLinkClass, PageContainer, PageHeader, Section } from "@/components/layout/page";
import { COMMUNITY_RULES } from "@/features/forum/rules";

/** SPEC "Moderation and community rules" and "Anonymity inside the forum", in plain words. */
export default function GuidelinesPage() {
  return (
    <PageContainer as="article" width="reading">
      <PageHeader
        title="Community guidelines"
        description="The forum is for honest, useful notes about courses and teaching. These rules keep it fair to students and instructors."
      />
      <div className="flex flex-col gap-12 text-body-md text-body">
        <Section id="rules" title="The rules">
          <ol className="flex list-decimal flex-col gap-2 pl-6">
            {COMMUNITY_RULES.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ol>
          <p className="mt-4">
            Criticism of how a course is taught is welcome. Comments about an instructor&apos;s appearance, health, family or private
            life are not.
          </p>
        </Section>

        <Section id="moderation" title="How moderation works">
          <ul className="flex list-disc flex-col gap-2 pl-6">
            <li>Email addresses and phone numbers are removed from every post before anyone reads it.</li>
            <li>An automatic check reads each post when you submit it. Most posts appear at once.</li>
            <li>
              A post that might identify someone, or that claims misconduct, waits for a person to read it. A post that is clearly
              abusive is not published, and you see why. If you think that was a mistake, you can ask for human review.
            </li>
            <li>If the automatic check is unavailable, your post waits for a moderator instead of appearing straight away.</li>
            <li>Anyone can report a post or comment. Moderators read every report.</li>
            <li>
              Three posts removed by a moderator suspend an account from posting, commenting and voting for 30 days. You can still log
              in and read.
            </li>
          </ul>
        </Section>

        <Section id="anonymity" title="What others see">
          <ul className="flex list-disc flex-col gap-2 pl-6">
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
        </Section>

        <Section id="instructors" title="Instructors">
          <p>
            Instructors cannot reply on the forum for now. Report anything that crosses a line, and take concerns about misconduct to
            the University instead of posting them.
          </p>
        </Section>
      </div>
    </PageContainer>
  );
}
