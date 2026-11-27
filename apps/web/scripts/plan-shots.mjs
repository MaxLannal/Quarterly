// Dev helper: screenshots of a filled planner (mock data). Usage: node scripts/plan-shots.mjs <outDir> [width]
import { chromium } from "@playwright/test";
const out = process.argv[2];
const W = Number(process.argv[3] ?? 1440);
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: W, height: 900 } });
await p.goto("http://127.0.0.1:5190/plan", { waitUntil: "networkidle" });
await p.getByRole("button", { name: "+ Program" }).click();
const dlg = p.getByRole("dialog", { name: "Programs" });
await dlg.getByRole("checkbox", { name: "Fake Program" }).check();
await dlg.getByRole("button", { name: "Save programs" }).click();
const add = async (code, term) => {
  const drawer = p.getByTestId("plan-drawer");
  if (!(await drawer.isVisible())) await p.getByRole("button", { name: "Requirements", exact: true }).click();
  const node = drawer.getByRole("button", { name: /^Fake introductory sequence/ });
  if ((await node.getAttribute("aria-expanded")) !== "true") await node.click();
  await p.getByRole("button", { name: `Add ${code} to a quarter` }).click();
  await p.getByRole("dialog", { name: `Add ${code} to…` }).getByRole("button", { name: term, exact: true }).click();
};
await add("TEST 10000", "Autumn 2099");
await add("TEST 10100", "Autumn 2099");
await add("TEST 10200", "Winter 2100");
await p.waitForTimeout(600);
await p.screenshot({ path: `${out}/plan-drawer-${W}.png` });
await p.getByTestId("plan-drawer").getByRole("button", { name: "Close panel" }).click();
await p.waitForTimeout(500);
await p.screenshot({ path: `${out}/plan-${W}.png` });
await b.close();
console.log("ok");
