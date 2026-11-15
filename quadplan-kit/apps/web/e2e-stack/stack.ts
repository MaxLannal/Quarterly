import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Node-side helpers for the stack journeys: the Docker Compose project lives two folders up
// (quadplan-kit/). STACK_COMPOSE_DIR overrides it.
const here = path.dirname(fileURLToPath(import.meta.url));
export const COMPOSE_DIR = process.env.STACK_COMPOSE_DIR ?? path.resolve(here, "../../..");

function compose(args: string[]): string {
  return execFileSync("docker", ["compose", ...args], { cwd: COMPOSE_DIR, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * The 6-digit sign-up code for `pendingId`, read from the API log. The console email backend
 * prints `[email:console] kind=signup_code pending_id=... code=NNNNNN` (never the address).
 */
export async function signupCode(pendingId: string, timeoutMs = 20_000): Promise<string> {
  const line = new RegExp(`\\[email:console\\] kind=signup_code pending_id=${pendingId.replace(/[^A-Za-z0-9_-]/g, "")} code=(\\d{6})`);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const match = line.exec(compose(["logs", "--no-color", "--since", "15m", "api"]));
    if (match?.[1]) return match[1];
    await sleep(500);
  }
  throw new Error(`no sign-up code for pending_id ${pendingId} in the api log`);
}

/** Clears the rate-limit counters (`rl:*`) so repeated runs stay under the per-day limits. */
export function resetRateLimits(): number {
  const keys = compose(["exec", "-T", "redis", "redis-cli", "--scan", "--pattern", "rl:*"])
    .split("\n")
    .map((k) => k.trim())
    .filter(Boolean);
  for (let i = 0; i < keys.length; i += 200) compose(["exec", "-T", "redis", "redis-cli", "DEL", ...keys.slice(i, i + 200)]);
  return keys.length;
}

/** A fresh username and fake @uchicago.edu address per run (the database persists). */
export function freshIdentity(prefix: string) {
  const tag = randomBytes(4).toString("hex");
  return { username: `e2e-${prefix}-${tag}`, email: `e2e${tag}${randomBytes(2).toString("hex")}@uchicago.edu`, password: `e2e pass ${tag} phrase` };
}
