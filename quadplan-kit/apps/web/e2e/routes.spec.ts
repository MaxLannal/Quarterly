import { expect, test } from "@playwright/test";

// Every row of SPEC "Sitemap and every page" renders.
const ROUTES: [string, string][] = [
  ["/", "Quarterly"],
  ["/onboarding", "Planner setup"],
  ["/plan", "Planner"],
  ["/plans", "My plans"],
  ["/plans/compare", "Compare plans"],
  ["/courses", "Course search"],
  ["/courses/MATH%2020700", "Course"],
  ["/courses/MATH%2020700/i/jane-doe", "Course × instructor forum"],
  ["/courses/MATH%2020700/i/jane-doe/t/1", "Thread"],
  ["/instructors", "Instructors"],
  ["/instructors/jane-doe", "Instructor"],
  ["/programs", "Program explorer"],
  ["/programs/cmsc-bs", "Program"],
  ["/signup", "Create an account"],
  ["/login", "Log in"],
  ["/account", "Account"],
  ["/guidelines", "Community guidelines"],
  ["/privacy", "Privacy"],
  ["/about", "About"],
  ["/admin/review", "Curator console"],
];

for (const [path, heading] of ROUTES) {
  test(`route ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading, exact: true })).toBeVisible();
  });
}
