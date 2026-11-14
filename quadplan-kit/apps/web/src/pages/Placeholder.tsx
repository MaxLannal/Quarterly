import { EmptyState, PageContainer, PageHeader } from "@/components/layout/page";

interface PlaceholderProps {
  title: string;
  route: string;
  prompt: string;
}

export function Placeholder({ title, route, prompt }: PlaceholderProps) {
  return (
    <PageContainer width="reading" as="section">
      <PageHeader title={title} size="md" />
      <EmptyState title="Not built yet">
        Placeholder for <code className="rounded-xs bg-surface-strong px-1 font-mono text-caption text-ink">{route}</code>. Built in prompt {prompt}.
      </EmptyState>
    </PageContainer>
  );
}
