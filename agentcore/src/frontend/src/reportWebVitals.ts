import type { ReportHandler } from "web-vitals";
import { initWebVitalsTelemetry } from "./telemetry/webVitals";

const reportWebVitals = (onPerfEntry?: ReportHandler) => {
  initWebVitalsTelemetry();
  if (onPerfEntry && onPerfEntry instanceof Function) {
    import("web-vitals").then(({ getCLS, getFID, getFCP, getLCP, getTTFB }) => {
      getCLS(onPerfEntry);
      getFID(onPerfEntry);
      getFCP(onPerfEntry);
      getLCP(onPerfEntry);
      getTTFB(onPerfEntry);
    });
  }
};

export default reportWebVitals;
