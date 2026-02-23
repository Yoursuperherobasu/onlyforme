import { getAppInsights } from "./appInsights";

export function initWebVitalsTelemetry(): void {
  try {
    if (import.meta.env.VITE_FE_WEBVITALS_ENABLED !== "true") {
      return;
    }
    const appInsights = getAppInsights();
    if (!appInsights) {
      return;
    }
    import("web-vitals").then(({ getCLS, getFID, getFCP, getLCP, getTTFB }) => {
      const send = (metric: { name: string; value: number }) => {
        try {
          appInsights.trackMetric({ name: metric.name, average: metric.value });
        } catch {
          // Do nothing
        }
      };
      getCLS(send);
      getFID(send);
      getFCP(send);
      getLCP(send);
      getTTFB(send);
    }).catch(() => {
      // Do nothing
    });
  } catch {
    // Do nothing
  }
}
