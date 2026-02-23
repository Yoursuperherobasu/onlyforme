import { getAppInsights } from "./appInsights";

export function initFrontendErrorTracking(): void {
  try {
    if (import.meta.env.VITE_FE_ERROR_TRACKING_ENABLED !== "true") {
      return;
    }
    const appInsights = getAppInsights();
    if (!appInsights) {
      return;
    }
    window.addEventListener("error", (event) => {
      try {
        appInsights.trackException({
          exception: event.error || new Error(event.message),
          properties: { type: "window.error" },
        });
      } catch {
        // Do nothing
      }
    });
    window.addEventListener("unhandledrejection", (event) => {
      try {
        const err = event.reason instanceof Error ? event.reason : new Error(String(event.reason));
        appInsights.trackException({
          exception: err,
          properties: { type: "unhandledrejection" },
        });
      } catch {
        // Do nothing
      }
    });
  } catch {
    // Do nothing
  }
}
