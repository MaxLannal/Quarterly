import { useRef } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { LoadingState, PageContainer, PageHeader, Section, standaloneLinkClass } from "@/components/layout/page";
import { useSession } from "@/features/auth/session";
import { useForumPage, usePost } from "@/features/forum/api";
import { CommentForm, CommentTree } from "@/features/forum/CommentTree";
import { pagePath } from "@/features/forum/format";
import { LoginRequired } from "@/features/forum/parts";
import { PostCard } from "@/features/forum/PostCard";
import "@/features/courses/glass.css";

function Thread({ code, slug, id }: { code: string; slug: string; id: number }) {
  const page = useForumPage(code, slug);
  const post = usePost(id);
  const navigate = useNavigate();
  const replyRef = useRef<HTMLDivElement>(null);
  const back = pagePath(code, slug);

  if (page.isLoading || post.isLoading) {
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title="Thread" size="md" />
        <LoadingState label="Loading the thread" />
      </PageContainer>
    );
  }
  if (!page.data || !post.data || post.data.page_id !== page.data.id) {
    const missing = (post.error instanceof ApiError && post.error.status === 404) || (post.data && page.data && post.data.page_id !== page.data.id);
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title={missing ? "Thread not found" : "Thread"} size="md" />
        <div className="flex flex-col gap-3">
          <p className="text-body">{missing ? "This post does not exist, or it was removed." : "Could not load this thread."}</p>
          <Link to={back} className={standaloneLinkClass}>
            Back to the forum page
          </Link>
        </div>
      </PageContainer>
    );
  }

  const p = post.data;
  const visible = p.status === "visible";
  const comments = p.comments ?? [];
  return (
    <PageContainer as="article" width="reading" className="flex flex-col gap-10 sm:pt-12">
      <Link to={back} className="qg-pill self-start">
        <span aria-hidden="true" className="text-primary">←</span>
        <span className="font-mono text-[12px] uppercase tracking-[0.14em] text-ink">{page.data.course_code}</span>
        <span>with {page.data.instructor.display_name}</span>
      </Link>
      <PostCard
        post={p}
        page={page.data}
        headingLevel={1}
        onReply={() => replyRef.current?.querySelector("textarea")?.focus()}
        onDeleted={() => navigate(back)}
      />
      <Section id="comments" title={`Comments (${p.n_comments ?? 0})`}
        description={comments.length > 0 ? "Best first." : undefined} size="md">
        <div className="flex flex-col gap-6">
          {visible ? (
            <div ref={replyRef}>
              <CommentForm postId={p.id} />
            </div>
          ) : (
            <p className="text-body-sm text-muted">Replies open once the post is published.</p>
          )}
          <CommentTree comments={comments} postId={p.id} canReply={visible} />
        </div>
      </Section>
    </PageContainer>
  );
}

export default function ThreadPage() {
  const { code = "", instructor = "", id = "" } = useParams();
  const session = useSession();
  if (session.status === "loading") {
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title="Thread" size="md" />
        <LoadingState label="Checking your login" />
      </PageContainer>
    );
  }
  if (session.status === "anonymous") return <LoginRequired title="Thread" eyebrow={code} />;
  return <Thread code={code} slug={instructor} id={Number(id)} />;
}
