import { resetRateLimits } from "./stack";

// The stack keeps its Redis between runs; logged-out generation allows 3 runs per IP per day,
// so each run starts from empty rate-limit counters (rl:* keys only).
export default function globalSetup() {
  resetRateLimits();
}
