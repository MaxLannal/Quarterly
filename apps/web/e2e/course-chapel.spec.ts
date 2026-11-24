import { expect, test, type Page } from "@playwright/test";

// The homepage: Rockefeller Chapel filling the first screen, drawn with the catalog's course
// titles (features/home/CourseChapel.tsx). These tests hold for the WebGL picture and for the
// plain-canvas fallback alike.

type ChapelCanvas = HTMLCanvasElement & { chapel?: { courseAt(x: number, y: number): string | null } };

async function chapelReady(page: Page) {
  const chapel = page.getByRole("img", { name: /Rockefeller Chapel, drawn with the titles of courses/ });
  await expect(chapel).toHaveAttribute("data-state", "ready", { timeout: 15_000 });
  return chapel;
}

/** A point (relative to the picture) that has a course title under it, inside the chapel. */
async function pointOverTitle(page: Page, x0: number, x1: number, y0: number, y1: number) {
  const point = await page.evaluate(
    ({ x0, x1, y0, y1 }) => {
      const c = document.querySelector("canvas.course-chapel") as ChapelCanvas | null;
      for (let y = y0; y < y1; y += 5) for (let x = x0; x < x1; x += 7) if (c?.chapel?.courseAt(x, y)) return { x, y };
      return null;
    },
    { x0, x1, y0, y1 },
  );
  expect(point).not.toBeNull();
  return point!;
}

test("the homepage is Rockefeller Chapel drawn with real course titles, loaded from our own server", async ({ page }) => {
  const data: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("course-chapel")) data.push(new URL(r.url()).pathname);
  });
  await page.goto("/");
  const chapel = await chapelReady(page);
  expect(Number(await chapel.getAttribute("data-glyphs"))).toBeGreaterThan(10_000);
  await expect(chapel).toHaveAttribute("data-placement", "side");
  expect(data).toEqual(["/home/course-chapel.json"]);
  // the controls sit on the picture and still work
  await expect(page.getByRole("heading", { level: 1, name: "The Best of UChicago, within your reach." })).toBeVisible();
  // the buttons still work on the picture (the question bar went in issue #15)
  await page.getByRole("link", { name: "Start planning" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
});

test("hovering a title names its course, and a click opens that course", async ({ page }) => {
  await page.goto("/");
  const chapel = await chapelReady(page);
  const box = (await chapel.boundingBox())!;
  const p = await pointOverTitle(page, box.width * 0.55, box.width * 0.8, box.height * 0.3, box.height * 0.6);
  await page.mouse.move(box.x + p.x - 40, box.y + p.y);
  await page.mouse.move(box.x + p.x, box.y + p.y, { steps: 4 });
  const label = page.locator(".course-chapel-label");
  await expect(label).toHaveAttribute("data-visible", "true");
  // let the parallax settle under the still mouse, then read what is under it now
  await page.waitForTimeout(1500);
  const code = await chapel.getAttribute("data-hover");
  expect(code).toMatch(/^[A-Z]{4} \d{5}$/);
  await expect(label).toContainText(code!);
  await page.mouse.click(box.x + p.x, box.y + p.y);
  await expect(page).toHaveURL(`/courses/${encodeURIComponent(code!)}`);
});

test("nothing opens from the picture behind the controls", async ({ page }) => {
  await page.goto("/");
  const chapel = await chapelReady(page);
  const h1 = (await page.getByRole("heading", { level: 1, name: "The Best of UChicago, within your reach." }).boundingBox())!;
  await page.mouse.move(h1.x + h1.width / 2, h1.y + h1.height / 2);
  await expect(chapel).toHaveAttribute("data-hover", "");
  await page.mouse.click(h1.x + h1.width / 2, h1.y + h1.height / 2);
  await expect(page).toHaveURL("/");
});

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });
  test("the picture is still", async ({ page }) => {
    await page.goto("/");
    const chapel = await chapelReady(page);
    await page.waitForTimeout(300);
    const a = await chapel.screenshot();
    await page.waitForTimeout(700);
    const b = await chapel.screenshot();
    expect(a.equals(b)).toBe(true);
  });
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });
  test("the chapel's front fills the screen and the controls sit under its spires", async ({ page }) => {
    await page.goto("/");
    const chapel = await chapelReady(page);
    await expect(chapel).toHaveAttribute("data-placement", "bottom");
    const hero = (await chapel.boundingBox())!;
    const h1 = (await page.getByRole("heading", { level: 1, name: "The Best of UChicago, within your reach." }).boundingBox())!;
    expect(h1.y - hero.y).toBeGreaterThan(hero.height * 0.5);
    expect(hero.height).toBeGreaterThan(844 * 0.8);
  });
});
