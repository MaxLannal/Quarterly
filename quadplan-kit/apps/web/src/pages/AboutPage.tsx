import { Link } from "react-router-dom";
import { inlineLinkClass, PageContainer, PageHeader } from "@/components/layout/page";

/** SPEC sitemap: About holds the disclaimers. Text agreed by Richard (DF-12, 2026-11-14). */
export default function AboutPage() {
  return (
    <PageContainer as="article" width="reading" className="flex flex-col gap-6 text-body-md text-body">
      <PageHeader title="About" eyebrow="Quarterly" className="mb-2" />
      <p>
        Quarterly is a student project. It is not run by, connected to or endorsed by the University of Chicago.
      </p>
      <p>
        The planner checks your plan against the published College Catalog, but it can be wrong or out of date. Your
        adviser and the University&apos;s official degree audit always have the final word on what you need to graduate.
      </p>
      <p>
        Forum posts are students&apos; own opinions. Other students only see a pseudonym that is different on every page.
        Anyone can report a post, and moderators take down what breaks the{" "}
        <Link to="/guidelines" className={inlineLinkClass}>
          community guidelines
        </Link>
        . What we store about you is on the{" "}
        <Link to="/privacy" className={inlineLinkClass}>
          privacy page
        </Link>
        .
      </p>
    </PageContainer>
  );
}
