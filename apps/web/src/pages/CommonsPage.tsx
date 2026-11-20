import { TypeHero } from "@/components/brand/TypeHero";

/** Placeholder (docs/BEST-OF-UCHICAGO-PLAN.md): the "commons" work stream builds this page. */
export default function CommonsPage() {
  return (
    <TypeHero
      shape="arcade"
      label="A cloister arcade drawn with the titles of real courses"
      kicker="The Commons"
      title={<>Ask the quad. <em>Someone</em> knows.</>}
    />
  );
}
