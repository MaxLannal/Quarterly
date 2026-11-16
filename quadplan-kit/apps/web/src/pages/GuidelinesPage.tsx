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
      <div className="flex flex-col gap-8 text-body-md text-body">
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
            <li>Posts and comments appear as soon as you submit them. Nothing reads them first.</li>
            <li>Anyone can report a post or comment. Moderators read every report and take down what breaks these guidelines.</li>
            <li>
              When a moderator removes a post, they may also suspend its author from posting, commenting and voting for a while. That is
              always a person&apos;s decision, never automatic. A suspended account can still log in and read.
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
