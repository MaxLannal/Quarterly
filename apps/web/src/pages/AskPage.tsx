import { TypeHero } from "@/components/brand/TypeHero";

/** Placeholder (docs/BEST-OF-UCHICAGO-PLAN.md): the "ask" work stream builds this page. */
export default function AskPage() {
  return (
    <TypeHero
      shape="arch"
      label="A Gothic window drawn with the titles of real courses"
      kicker="Ask Quarterly"
      title={<>Ask <em>anything</em> about UChicago.</>}
    />
  );
}
