// Screenshots of the running mock-data app (dev helper for the dark-glass redesign).
// Usage: node scripts/shoot.mjs <outDir> <path> [<path> ...]
//   env: BASE (default http://127.0.0.1:5190), W/H (default 1440x900), FULL=1 for full-page,
//        WAIT (ms, default 1800), LOGIN=1 to sign in as the mock student first.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const [outDir, ...paths] = process.argv.slice(2);
const base = process.env.BASE ?? "http://127.0.0.1:5190";
const W = Number(process.env.W ?? 1440);
const H = Number(process.env.H ?? 900);
const wait = Number(process.env.WAIT ?? 1800);
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on("pageerror", (e) => console.log("pageerror:", e.message));
for (const p of paths) {
  await page.goto(base + p, { waitUntil: "networkidle" });
  await page.waitForTimeout(wait);
  const name = (p.replace(/[/?=&]+/g, "_").replace(/^_/, "") || "home") + `-${W}.png`;
  await page.screenshot({ path: `${outDir}/${name}`, fullPage: process.env.FULL === "1" });
  console.log(`${outDir}/${name}`);
}
await browser.close();
