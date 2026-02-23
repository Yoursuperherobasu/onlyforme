import { ApplicationInsights } from "@microsoft/applicationinsights-web";

let appInsightsInstance: ApplicationInsights | null = null;

export function initAppInsights(): void {
  try {
    const enabled = import.meta.env.VITE_APPINSIGHTS_ENABLED === "true";
    const connectionString = import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING;
    if (!enabled || !connectionString || typeof connectionString !== "string") {
      return;
    }
    appInsightsInstance = new ApplicationInsights({
      config: {
        connectionString,
        enableAutoRouteTracking: true,
        enableAjaxPerfTracking: true,
        enableCorsCorrelation: true,
        distributedTracingMode: 2,
      },
    });
    appInsightsInstance.loadAppInsights();
  } catch {
    // Do nothing
  }
}

export function getAppInsights(): ApplicationInsights | null {
  return appInsightsInstance;
}

export function getTraceparentHeader(): string | null {
  try {
    if (import.meta.env.VITE_FE_TRACEPARENT_ENABLED !== "true") {
      return null;
    }
    const ai = appInsightsInstance;
    if (!ai?.core?.getTraceCtx) {
      return null;
    }
    const ctx = ai.core.getTraceCtx(false);
    const traceId = ctx?.getTraceId?.();
    const spanId = ctx?.getSpanId?.();
    if (!traceId || !spanId) {
      return null;
    }
    return `00-${traceId}-${spanId}-01`;
  } catch {
    return null;
  }
}
