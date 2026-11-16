import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

// FEEDBACK "ASCII Scene" (2026-11-16): the live chapel scene on the homepage. With SCREENSHOTS=1
// the proof screenshots go to docs/screenshots/ascii-<state>-<width>.png.

const OUT = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../docs/screenshots",
);

type SceneEl = HTMLElement & {
  _lv?: unknown;
  _sprites?: { kind: string }[];
  _gust?: unknown;
  _geo?: { cw: number; ch: number };
};

async function sceneReady(page: Page) {
  const scene = page.locator("ascii-scene");
  await expect(scene).toBeVisible();
  await page.waitForFunction(
    () =>
      Boolean((document.querySelector("ascii-scene") as SceneEl | null)?._lv),
    null,
    { timeout: 15_000 },
  );
  return scene;
}

async function setState(page: Page, time: string, weather: string) {
  await page.locator("ascii-scene").evaluate(
    (el, state) => {
      el.setAttribute("time", state.time);
      el.setAttribute("weather", state.weather);
    },
    { time, weather },
  );
  await page.waitForTimeout(400);
}

test("the homepage shows the chapel scene, with its weather from our own server; Open-Meteo is credited on /about", async ({
  page,
}) => {
  const weather: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("weather")) weather.push(new URL(r.url()).pathname);
  });
  await page.goto("/");
  await sceneReady(page);
  await expect(
    page.getByRole("img", { name: /Rockefeller Chapel/ }),
  ).toBeVisible();
  await expect.poll(() => weather).toContain("/api/weather");
  expect(weather.every((p) => p === "/api/weather")).toBe(true);
  await page.goto("/about");
  await expect(
    page.getByRole("link", { name: "Open-Meteo.com" }),
  ).toHaveAttribute("href", "https://open-meteo.com/");
});

test("a click sends a shooting star down the night sky; by day it sends up birds", async ({
  page,
}) => {
  await page.goto("/");
  const scene = await sceneReady(page);
  await setState(page, "night", "clear");
  const box = (await scene.boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.2, box.y + box.height * 0.15);
  const sprites = () =>
    scene.evaluate((el: SceneEl) => (el._sprites ?? []).map((s) => s.kind));
  await expect.poll(sprites).toEqual(["meteor"]);
  await setState(page, "noon", "clear");
  await page.waitForTimeout(1300); // the shooting star has gone
  await page.mouse.click(box.x + box.width * 0.2, box.y + box.height * 0.15);
  await expect.poll(sprites).toEqual(["birds"]);
});

test("sweeping the pointer across the trees makes them sway", async ({
  page,
}) => {
  await page.goto("/");
  const scene = await sceneReady(page);
  const box = (await scene.boundingBox())!;
  const y = box.y + box.height * 0.62;
  await page.mouse.move(box.x + box.width * 0.05, y);
  await page.mouse.move(box.x + box.width * 0.6, y, { steps: 6 });
  await expect
    .poll(() => scene.evaluate((el: SceneEl) => Boolean(el._gust)))
    .toBe(true);
});

test("with reduced motion the scene stays still: no shooting star, no sway", async ({
  browser,
}) => {
  const context = await browser.newContext({
    reducedMotion: "reduce",
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  await page.goto("/");
  const scene = await sceneReady(page);
  await setState(page, "night", "clear");
  const box = (await scene.boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.2, box.y + box.height * 0.15);
  await page.mouse.move(box.x + box.width * 0.05, box.y + box.height * 0.62);
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.62, {
    steps: 6,
  });
  await page.waitForTimeout(300);
  expect(
    await scene.evaluate((el: SceneEl) => ({
      sprites: el._sprites?.length ?? 0,
      gust: Boolean(el._gust),
    })),
  ).toEqual({ sprites: 0, gust: false });
  await context.close();
});

test("on a phone the scene fits the screen: no sideways scrolling", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage();
  await page.goto("/");
  await sceneReady(page);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await context.close();
});

const STATES: [string, string][] = [
  ["noon", "clear"],
  ["golden", "clear"],
  ["night", "clear"],
  ["noon", "rain"],
  ["night", "snow"],
  ["morning", "fog"],
];

test("screenshots: six times and weathers at 1440, 1024 and 390 wide", async ({
  browser,
}) => {
  test.skip(
    !process.env.SCREENSHOTS,
    "proof screenshots only with SCREENSHOTS=1",
  );
  test.setTimeout(120_000);
  mkdirSync(OUT, { recursive: true });
  for (const width of [1440, 1024, 390]) {
    const context = await browser.newContext({
      viewport: { width, height: width === 390 ? 844 : 900 },
    });
    const page = await context.newPage();
    await page.goto("/");
    const scene = await sceneReady(page);
    for (const [time, weather] of STATES) {
      if (
        width !== 1440 &&
        !(time === "night" && weather === "clear") &&
        !(time === "noon" && weather === "rain")
      )
        continue;
      await setState(page, time, weather);
      await page.waitForTimeout(600);
      const target =
        width === 390 ? scene : page.locator("main section").first();
      await target.screenshot({
        path: `${OUT}/ascii-${time}-${weather}-${width}.png`,
      });
    }
    await context.close();
  }
});
