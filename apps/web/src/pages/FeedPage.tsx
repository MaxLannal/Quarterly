import { TypeHero } from "@/components/brand/TypeHero";

/** Placeholder (docs/BEST-OF-UCHICAGO-PLAN.md): the "feed" work stream builds this page. */
export default function FeedPage() {
  return (
    <TypeHero
      shape="river"
      label="Bands of course titles flowing across the page"
      kicker="The Feed"
      title={<>A river of <em>ideas</em>, chosen for you.</>}
    />
  );
}
