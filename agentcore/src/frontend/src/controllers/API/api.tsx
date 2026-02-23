import axios, {
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
} from "axios";
import * as fetchIntercept from "fetch-intercept";
import { useEffect } from "react";
import { Cookies } from "react-cookie";

import { baseURL } from "@/customization/constants";
import { useCustomApiHeaders } from "@/customization/hooks/use-custom-api-headers";
import { customGetAccessToken } from "@/customization/utils/custom-get-access-token";

import useAuthStore from "@/stores/authStore";
import { useUtilityStore } from "@/stores/utilityStore";
import useAlertStore from "@/stores/alertStore";
import useAgentStore from "@/stores/agentStore";

import { BuildStatus, type EventDeliveryType } from "../../constants/enums";
import { checkDuplicateRequestAndStoreRequest } from "./helpers/check-duplicate-requests";
import { useLogout, useRefreshAccessToken } from "./queries/auth";
import { getAppInsights, getTraceparentHeader } from "../../telemetry/appInsights";

/* Map<url, startTime[]> for fetch duration tracking (FIFO per URL) */
const fetchStartTimes = new Map<string, number[]>();

function depId(): string {
  return typeof crypto?.randomUUID === "function"
    ? crypto.randomUUID()
    : `dep-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/* =========================================================
   AXIOS INSTANCE
========================================================= */

const api: AxiosInstance = axios.create({
  baseURL,
  withCredentials: true,
});

const _cookies = new Cookies();

/* =========================================================
   API INTERCEPTOR
========================================================= */

function ApiInterceptor() {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const accessToken = useAuthStore((state) => state.accessToken);
  const authenticationErrorCount = useAuthStore(
    (state) => state.authenticationErrorCount,
  );
  const setAuthenticationErrorCount = useAuthStore(
    (state) => state.setAuthenticationErrorCount,
  );

  const { mutate: mutationLogout } = useLogout();
  const { mutate: mutationRenewAccessToken } = useRefreshAccessToken();
  const isLoginPage = location.pathname.includes("login");
  const customHeaders = useCustomApiHeaders();

  const setHealthCheckTimeout = useUtilityStore(
    (state) => state.setHealthCheckTimeout,
  );

  useEffect(() => {
    // Define helper functions INSIDE useEffect (like the old code)
    const isAuthorizedURL = (url) => {
      if (!url) return false;
      return url.includes("auto_login");
    };

    const isExternalURL = (url: string): boolean => {
      const EXTERNAL_DOMAINS = [
        "https://raw.githubusercontent.com",
        "https://api.github.com",
        "https://api.segment.io",
        "https://cdn.sprig.com",
      ];

      try {
        const parsedURL = new URL(url);
        return EXTERNAL_DOMAINS.some((domain) => parsedURL.origin === domain);
      } catch {
        return false;
      }
    };

    const unregister = fetchIntercept.register({
      request: (url, config) => {
        if (import.meta.env.VITE_FE_API_TELEMETRY_ENABLED === "true") {
          const arr = fetchStartTimes.get(url) ?? [];
          arr.push(performance.now());
          fetchStartTimes.set(url, arr);
        }
        const accessToken = customGetAccessToken();
        config.headers = config?.headers ?? {};

        if (!isExternalURL(url)) {
          if (accessToken && !isAuthorizedURL(config?.url)) {
            config.headers["Authorization"] = `Bearer ${accessToken}`;
          }

          for (const [key, value] of Object.entries(customHeaders)) {
            config.headers[key] = value;
          }

          const traceparent = getTraceparentHeader();
          if (traceparent) {
            config.headers["traceparent"] = traceparent;
          }
        }

        return [url, config];
      },
      response: (response) => {
        try {
          if (import.meta.env.VITE_FE_API_TELEMETRY_ENABLED === "true" && response.status >= 400) {
            const appInsights = getAppInsights();
            if (appInsights) {
              const url = response.url ?? response.request?.url ?? "";
              const arr = fetchStartTimes.get(url);
              const startTime = arr?.shift();
              if (arr?.length === 0) fetchStartTimes.delete(url);
              const durationMs = typeof startTime === "number" ? performance.now() - startTime : 0;
              appInsights.trackDependencyData({
                id: depId(),
                name: url,
                duration: durationMs,
                success: false,
                responseCode: response.status,
                type: "Fetch",
              });
            }
          }
        } catch {
          // Do nothing
        }
        return response;
      },
      responseError: (error) => {
        try {
          if (import.meta.env.VITE_FE_API_TELEMETRY_ENABLED === "true") {
            const appInsights = getAppInsights();
            if (appInsights) {
              appInsights.trackException({
                exception: error instanceof Error ? error : new Error(String(error)),
                properties: { type: "fetch.error" },
              });
              const url = error?.request?.url ?? "";
              const arr = url ? fetchStartTimes.get(url) : undefined;
              const startTime = arr?.shift();
              if (arr?.length === 0 && url) fetchStartTimes.delete(url);
              const durationMs = typeof startTime === "number" ? performance.now() - startTime : 0;
              appInsights.trackDependencyData({
                id: depId(),
                name: url || "fetch",
                duration: durationMs,
                success: false,
                responseCode: 0,
                type: "Fetch",
              });
            }
          }
        } catch {
          // Do nothing
        }
        return Promise.reject(error);
      },
    });

    const interceptor = api.interceptors.response.use(
      (response) => {
        setHealthCheckTimeout(null);
        return response;
      },
      async (error: AxiosError) => {
        try {
          if (import.meta.env.VITE_FE_API_TELEMETRY_ENABLED === "true") {
            const appInsights = getAppInsights();
            if (appInsights) {
              const cfg = error?.config as { __aiStartTime?: number } | undefined;
              const startTime = cfg?.__aiStartTime;
              const durationMs = typeof startTime === "number" ? performance.now() - startTime : 0;
              const url = error?.config?.url ?? "";
              const method = error?.config?.method ?? "GET";
              const status = error?.response?.status ?? 0;
              appInsights.trackDependencyData({
                id: depId(),
                name: `${method} ${url}`,
                duration: durationMs,
                success: false,
                responseCode: status,
                type: "HTTP",
              });
            }
          }
        } catch {
          // Do nothing
        }
        const isAuthenticationError =
          error?.response?.status === 403 || error?.response?.status === 401;

        const shouldRetryRefresh = !isAuthenticationError;

        if (shouldRetryRefresh) {
          if (
            error?.config?.url?.includes("github") ||
            error?.config?.url?.includes("public")
          ) {
            return Promise.reject(error);
          }
          const stillRefresh = checkErrorCount();
          if (!stillRefresh) {
            return Promise.reject(error);
          }

          await tryToRenewAccessToken(error);

          const accessToken = customGetAccessToken();

          if (!accessToken && error?.config?.url?.includes("login")) {
            return Promise.reject(error);
          }
        }

        await clearBuildVerticesState(error);

        return Promise.reject(error);
      },
    );

    const requestInterceptor = api.interceptors.request.use(
      async (config) => {
        const controller = new AbortController();
        try {
          checkDuplicateRequestAndStoreRequest(config);
        } catch (e) {
          const error = e as Error;
          controller.abort(error.message);
          console.error(error.message);
        }

        const accessToken = customGetAccessToken();

        if (accessToken && !isAuthorizedURL(config?.url)) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }

        const currentOrigin = window.location.origin;
        const requestUrl = new URL(config?.url as string, currentOrigin);

        const urlIsFromCurrentOrigin = requestUrl.origin === currentOrigin;
        if (urlIsFromCurrentOrigin) {
          for (const [key, value] of Object.entries(customHeaders)) {
            config.headers[key] = value;
          }
        }

        const traceparent = getTraceparentHeader();
        if (traceparent) {
          config.headers = config.headers ?? {};
          config.headers["traceparent"] = traceparent;
        }

        if (import.meta.env.VITE_FE_API_TELEMETRY_ENABLED === "true") {
          (config as { __aiStartTime?: number }).__aiStartTime = performance.now();
        }

        return {
          ...config,
          signal: controller.signal,
        };
      },
      (error) => {
        return Promise.reject(error);
      },
    );

    return () => {
      api.interceptors.response.eject(interceptor);
      api.interceptors.request.eject(requestInterceptor);
      unregister();
    };
  }, [accessToken, setErrorData, customHeaders]);

  function checkErrorCount() {
    if (isLoginPage) return;

    setAuthenticationErrorCount(authenticationErrorCount + 1);

    if (authenticationErrorCount > 3) {
      setAuthenticationErrorCount(0);
      mutationLogout();
      return false;
    }

    return true;
  }

  async function tryToRenewAccessToken(error: AxiosError) {
    if (isLoginPage) return;
    if (error.config?.headers) {
      for (const [key, value] of Object.entries(customHeaders)) {
        error.config.headers[key] = value;
      }
    }
    mutationRenewAccessToken(undefined, {
      onSuccess: async () => {
        setAuthenticationErrorCount(0);
        await remakeRequest(error);
        setAuthenticationErrorCount(0);
      },
      onError: (error) => {
        console.error(error);
        mutationLogout();
        return Promise.reject("Authentication error");
      },
    });
  }

  async function clearBuildVerticesState(error) {
    if (error?.response?.status === 500) {
      const vertices = useAgentStore.getState().verticesBuild;
      useAgentStore
        .getState()
        .updateBuildStatus(vertices?.verticesIds ?? [], BuildStatus.BUILT);
      useAgentStore.getState().setIsBuilding(false);
    }
  }

  async function remakeRequest(error: AxiosError) {
    const originalRequest = error.config as AxiosRequestConfig;

    try {
      const accessToken = customGetAccessToken();

      if (!accessToken) {
        throw new Error("Access token not found in cookies");
      }

      originalRequest.headers = {
        ...(originalRequest.headers as Record<string, string>),
        Authorization: `Bearer ${accessToken}`,
      };

      const response = await axios.request(originalRequest);
      return response.data;
    } catch (err) {
      throw err;
    }
  }

  return null;
}

/* =========================================================
   STREAMING
========================================================= */

export type StreamingRequestParams = {
  method: string;
  url: string;
  onData: (event: object) => Promise<boolean>;
  body?: object;
  onError?: (statusCode: number) => void;
  onNetworkError?: (error: Error) => void;
  buildController: AbortController;
  eventDeliveryConfig?: EventDeliveryType;
};

function sanitizeJsonString(jsonStr: string): string {
  return jsonStr
    .replace(/:\s*NaN\b/g, ": null")
    .replace(/\[\s*NaN\s*\]/g, "[null]")
    .replace(/,\s*NaN\s*,/g, ", null,")
    .replace(/,\s*NaN\s*\]/g, ", null]");
}

async function performStreamingRequest({
  method,
  url,
  onData,
  body,
  onError,
  onNetworkError,
  buildController,
}: StreamingRequestParams) {
  const headers = {
    "Content-Type": "application/json",
    Connection: "close",
  };

  const params = {
    method: method,
    headers: headers,
    signal: buildController.signal,
  };
  if (body) {
    params["body"] = JSON.stringify(body);
  }
  let current: string[] = [];
  const textDecoder = new TextDecoder();

  try {
    const response = await fetch(url, params);
    if (!response.ok) {
      if (onError) {
        onError(response.status);
      } else {
        throw new Error("Error in streaming request.");
      }
    }
    if (response.body === null) {
      return;
    }
    const reader = response.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      const decodedChunk = textDecoder.decode(value);
      const all = decodedChunk.split("\n\n");
      for (const string of all) {
        if (string.endsWith("}")) {
          const allString = current.join("") + string;
          let data: object;
          try {
            const sanitizedJson = sanitizeJsonString(allString);
            data = JSON.parse(sanitizedJson);
            current = [];
          } catch (_e) {
            current.push(string);
            continue;
          }
          const shouldContinue = await onData(data);
          if (!shouldContinue) {
            buildController.abort();
            return;
          }
        } else {
          current.push(string);
        }
      }
    }
    if (current.length > 0) {
      const allString = current.join("");
      if (allString) {
        const sanitizedJson = sanitizeJsonString(allString);
        const data = JSON.parse(sanitizedJson);
        await onData(data);
      }
    }
  } catch (e: any) {
    if (onNetworkError) {
      onNetworkError(e);
    } else {
      throw e;
    }
  }
}

export { api, ApiInterceptor, performStreamingRequest };
