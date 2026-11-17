// Screenshots of the real Docker build against the real API and seed data (no mocks).
//
//   make up && make seed
//   node apps/web/scripts/screenshots.mjs            (from the project root)
//
// Writes docs/screenshots/{planner,planner-issues,course-page,program-page}.png.
// BASE_URL overrides http://localhost:5173.
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:5173";
const OUT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../docs/screenshots");
const STORAGE_KEY = "quarterly.plans.v1"; // src/features/planner/localPlans.ts

// A first-year-and-a-bit plan for the Core and the Computer Science BS, 2026-27 catalog.
const QUARTERS = {
  "2026-AU": ["CMSC 14100", "MATH 15100", "HUMA 11000"],
  "2027-WI": ["CMSC 14200", "MATH 15200", "HUMA 11100"],
  "2027-SP": ["CMSC 14300", "MATH 15300", "HUMA 11200"],
  "2027-AU": ["CMSC 14400", "CMSC 27100", "SOSC 15100"],
};

function plansDoc(name, quarters) {
  let n = 0;
  const items = Object.entries(quarters).flatMap(([term, courses]) =>
    courses.map((course) => ({
      id: `shot-${++n}`,
      course,
      slot_ref: null,
      term,
      status: "planned",
      grading: "letter",
      locked: false,
      units: null,
    })),
  );
  const state = {
    catalog_year: "2026-27",
    entry_term: "2026-AU",
    entry_year_level: 1,
    items,
    credits: [],
    programs: [{ program_id: "core" }, { program_id: "cmsc-bs" }],
    goals: [],
    placements: ["MATH 15100"],
    overload_reasons: {},
  };
  const plan = { localId: "plan-screenshot", name, isPrimary: true, state, updatedDay: "2026-11-12", years: 4 };
  return { version: 1, activeId: plan.localId, plans: [plan] };
}

async function openPlanner(page, doc) {
  await page.goto(`${BASE}/`);
  await page.evaluate(([key, value]) => window.localStorage.setItem(key, value), [STORAGE_KEY, JSON.stringify(doc)]);
  await page.goto(`${BASE}/plan`);
  const badge = page.getByTestId("verifier-badge");
  // The badge shows "Checking…" until POST /verify answers.
  await badge.filter({ hasText: /Valid|\d+ (error|warning)s?/ }).filter({ hasNotText: /checking/i }).waitFor();
  await page.getByRole("tab", { name: /Issues/ }).click();
  await page.locator('[data-testid="course-card"]').first().waitFor();
  return (await badge.innerText()).trim();
}

async function shot(page, name) {
  await page.waitForLoadState("networkidle");
  const path = resolve(OUT, name);
  await page.screenshot({ path, fullPage: true });
  console.log(`wrote ${path}`);
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1680, height: 1050 }, deviceScaleFactor: 1 });
const page = await context.newPage();
const failed = [];
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 500) failed.push(`${r.status()} ${r.url()}`);
});

try {
  // 1. Planner: grid + requirement rail + Issues tab.
  console.log(`planner badge: ${await openPlanner(page, plansDoc("Core + CS BS", QUARTERS))}`);
  await shot(page, "planner.png");

  // 2. The same plan with CMSC 14100 and CMSC 14200 swapped: a prerequisite error (V03).
  const broken = {
    ...QUARTERS,
    "2026-AU": ["CMSC 14200", "MATH 15100", "HUMA 11000"],
    "2027-WI": ["CMSC 14100", "MATH 15200", "HUMA 11100"],
  };
  console.log(`planner (prerequisite error) badge: ${await openPlanner(page, plansDoc("Core + CS BS", broken))}`);
  const issue = page.getByRole("button", { name: /V03.*CMSC 14200/s }).first();
  await issue.click();
  await page.locator('[data-testid="course-card"][data-course="CMSC 14200"][data-highlighted="true"]').waitFor();
  await issue.scrollIntoViewIfNeeded();
  await shot(page, "planner-issues.png");

  // 3. Course page.
  await page.goto(`${BASE}/courses/${encodeURIComponent("CMSC 14200")}`);
  await page.getByRole("heading", { level: 1, name: /CMSC 14200/ }).waitFor();
  await page.getByRole("heading", { level: 2 }).first().waitFor();
  await shot(page, "course-page.png");

  // 4. Program page.
  await page.goto(`${BASE}/programs/cmsc-bs`);
  await page.getByRole("heading", { level: 1, name: /Computer Science/ }).waitFor();
  await shot(page, "program-page.png");
} finally {
  await browser.close();
}
if (failed.length) {
  console.error(`API errors while taking screenshots:\n${failed.join("\n")}`);
  process.exit(1);
}
