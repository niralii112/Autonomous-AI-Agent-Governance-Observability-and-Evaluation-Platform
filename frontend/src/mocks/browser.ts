import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";
import { platformHandlers } from "./platformHandlers";
import { governanceHandlers } from "./governanceHandlers";
import { approvalHandlers } from "./approvalHandlers";
import { traceHandlers } from "./traceHandlers";
import { extendedHandlers } from "./extendedHandlers";

export const worker = setupWorker(
  ...handlers,
  ...platformHandlers,
  ...governanceHandlers,
  ...approvalHandlers,
  ...traceHandlers,
  ...extendedHandlers
);
