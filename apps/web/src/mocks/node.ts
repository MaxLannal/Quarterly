import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** MSW for vitest (Node). */
export const server = setupServer(...handlers);
