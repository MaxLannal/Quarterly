import { expect, test } from "@playwright/test";

// Every row of SPEC "Sitemap and every page" renders.
const ROUTES: [string, string][] = [
  ["/", "The Best of UChicago, within your reach."],
  ["/onboarding", "Planner setup"],
  ["/plan", "Planner"],
  ["/plans", "My plans"],
  ["/plans/compare", "Compare plans"],
  ["/courses", "Catalog"],
  ["/courses/TEST%2010000", "TEST 10000 · Fake Introduction I"],
  ["/courses/MATH%2020700/i/jane-doe", "Course × instructor forum"],
  ["/courses/MATH%2020700/i/jane-doe/t/1", "Thread"],
  ["/instructors", "Forum"],
  ["/instructors/fake-instructor-a", "Fake Instructor A"],
  ["/programs", "Program explorer"],
  ["/programs/fake-major", "Fake Program"],
  ["/signup", "Create an account"],
  ["/login", "Welcome back"], // the redesign's sign-in title (docs/DESIGN.md "Maroon and night")
  ["/account", "Account"],
  ["/guidelines", "Community guidelines"],
  ["/privacy", "Privacy"],
  ["/about", "About"],
  ["/admin/review", "Curator console"],
  ["/admin/moderation", "Moderation queue"],
];

for (const [path, heading] of ROUTES) {
  test(`route ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading, exact: true })).toBeVisible();
  });
}
