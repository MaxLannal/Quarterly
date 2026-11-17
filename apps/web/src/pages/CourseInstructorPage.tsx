import { useParams } from "react-router-dom";
import { LoadingState, PageContainer, PageHeader } from "@/components/layout/page";
import { useSession } from "@/features/auth/session";
import { ForumPageView } from "@/features/forum/ForumPageView";
import { LoginRequired } from "@/features/forum/parts";

const TITLE = "Course × instructor forum";

export default function CourseInstructorPage() {
  const { code = "", instructor = "" } = useParams();
  const session = useSession();
  if (session.status === "loading") {
    return (
      <PageContainer as="section">
        <PageHeader title={TITLE} size="md" />
        <LoadingState label="Checking your login" />
      </PageContainer>
    );
  }
  if (session.status === "anonymous") return <LoginRequired title={TITLE} eyebrow={code} />;
  return <ForumPageView code={code} slug={instructor} />;
}
