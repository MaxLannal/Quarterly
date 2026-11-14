import { Link } from "react-router-dom";
import { EmptyState, PageContainer, PageHeader } from "@/components/layout/page";

interface PlaceholderProps {
  title: string;
}

/** A page whose content is not written yet. Plain words for students; no build notes on screen. */
export function Placeholder({ title }: PlaceholderProps) {
  return (
    <PageContainer width="reading" as="section">
      <PageHeader title={title} size="md" />
      <EmptyState title="Coming soon">
        This page is not written yet. <Link to="/">Go to the home page</Link>
      </EmptyState>
    </PageContainer>
  );
}
