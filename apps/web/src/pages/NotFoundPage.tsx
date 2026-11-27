import { Link } from "react-router-dom";
import { PageContainer, PageHeader, standaloneLinkClass } from "@/components/layout/page";

export default function NotFoundPage() {
  return (
    <PageContainer width="reading" as="section">
      <PageHeader title="Page not found" size="md" />
      <p>
        <Link to="/" className={standaloneLinkClass}>
          Go to the home page
        </Link>
      </p>
    </PageContainer>
  );
}
