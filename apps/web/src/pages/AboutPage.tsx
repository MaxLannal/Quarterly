import { Link } from "react-router-dom";
import { inlineLinkClass } from "@/components/layout/page";
import { EditorialPage, EditorialSection } from "@/features/auth/editorial";

/** SPEC sitemap: About holds the disclaimers. Text agreed by Richard (DF-12, 2026-11-14). */
export default function AboutPage() {
  return (
    <EditorialPage
      eyebrow="Quarterly // About"
      title="About"
      lede={
        <p>
          Quarterly is a student project. It is not run by, connected to or
          endorsed by the University of Chicago.
        </p>
      }
    >
      <EditorialSection id="planner" n={1} title="The planner">
        <p>
          The planner checks your plan against the published College Catalog, but
          it can be wrong or out of date. Your adviser and the University&apos;s
          official degree audit always have the final word on what you need to
          graduate.
        </p>
      </EditorialSection>
      <EditorialSection id="forum" n={2} title="The forum">
        <p>
          Forum posts are students&apos; own opinions. Other students only see a
          pseudonym that is different on every page. Anyone can report a post, and
          moderators take down what breaks the{" "}
          <Link to="/guidelines" className={inlineLinkClass}>
            community guidelines
          </Link>
          . What we store about you is on the{" "}
          <Link to="/privacy" className={inlineLinkClass}>
            privacy page
          </Link>
          .
        </p>
      </EditorialSection>
      <EditorialSection id="drawing" n={3} title="The drawing">
        <p>
          The reading room of Harper Memorial Library on the home page is an
          original drawing, made in code for Quarterly. It is not a photograph.
        </p>
      </EditorialSection>
    </EditorialPage>
  );
}
