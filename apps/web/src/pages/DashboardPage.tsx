import { TypeHero } from "@/components/brand/TypeHero";

/** Placeholder (docs/BEST-OF-UCHICAGO-PLAN.md): the "me" work stream builds this page. */
export default function DashboardPage() {
  return (
    <TypeHero
      shape="orbit"
      label="Rings of course titles orbiting a maroon sun"
      kicker="Your Quarterly"
      title={<>Everything you <em>are</em> becoming.</>}
    />
  );
}
