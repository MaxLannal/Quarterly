import { resetRateLimits } from "./stack";

// The journeys share the stack (and so the rate-limit counters) with whoever uses the app on
// this machine afterwards: clear them on the way out too, so a test run never uses up the
// owner's daily allowance of logged-out plan generations (3 per address).
export default function globalTeardown() {
  resetRateLimits();
}
