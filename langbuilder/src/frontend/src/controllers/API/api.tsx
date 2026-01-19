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
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";

import { BuildStatus, type EventDeliveryType } from "../../constants/enums";
import { checkDuplicateRequestAndStoreRequest } from "./helpers/check-duplicate-requests";
import { useLogout, useRefreshAccessToken } from "./queries/auth";

/* =========================================================
   AXIOS INSTANCE
========================================================= */

const api: AxiosInstance = axios.create({
  baseURL,
});

const _cookies = new Cookies();

/* =========================================================
   API INTERCEPTOR
========================================================= */

function ApiInterceptor() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const authenticationErrorCount = useAuthStore(
    (s) => s.authenticationErrorCount,
  );
  const setAuthenticationErrorCount = useAuthStore(
    (s) => s.setAuthenticationErrorCount,
  );

  const { mutate: mutationLogout } = useLogout();
  const { mutate: mutationRenewAccessToken } = useRefreshAccessToken();

  const customHeaders = useCustomApiHeaders();
  const setHealthCheckTimeout = useUtilityStore(
    (s) => s.setHealthCheckTimeout,
  );

  const isLoginPage = location.pathname.includes("login");

  useEffect(() => {
    /* ================= FETCH INTERCEPT ================= */

    const unregister = fetchIntercept.register({
      request: (url, config) => {
        const token = customGetAccessToken();

        if (!isExternalURL(url)) {
          if (token && !isAuthorizedURL(config?.url)) {
            config.headers["Authorization"] = `Bearer ${token}`;
          }

          for (const [key, value] of Object.entries(customHeaders)) {
            config.headers[key] = value;
          }
        }

        return [url, config];
      },
    });

    /* ================= RESPONSE INTERCEPTOR ================= */

    const responseInterceptor = api.interceptors.response.use(
      (response) => {
        setHealthCheckTimeout(null);
        return response;
      },
      async (error: AxiosError) => {
        const status = error?.response?.status;

        /* 🔥 DO NOT RETRY FOR 500 / 400 / ANY NON-AUTH ERROR */
        if (status !== 401 && status !== 403) {
          await clearBuildVerticesState(error);
          return Promise.reject(error);
        }

        /* 🔐 AUTH ERROR HANDLING ONLY */
        if (isLoginPage) {
          return Promise.reject(error);
        }

        const canRetry = checkErrorCount();
        if (!canRetry) {
          return Promise.reject(error);
        }

        try {
          await tryToRenewAccessToken(error);
        } catch (e) {
          return Promise.reject(e);
        }

        return Promise.reject(error);
      },
    );

    /* ================= REQUEST INTERCEPTOR ================= */

    const requestInterceptor = api.interceptors.request.use(
      async (config) => {
        const controller = new AbortController();

        try {
          checkDuplicateRequestAndStoreRequest(config);
        } catch (e) {
          controller.abort((e as Error).message);
        }

        const token = customGetAccessToken();
        if (token && !isAuthorizedURL(config?.url)) {
          config.headers["Authorization"] = `Bearer ${token}`;
        }

        for (const [key, value] of Object.entries(customHeaders)) {
          config.headers[key] = value;
        }

        return {
          ...config,
          signal: controller.signal,
        };
      },
      (error) => Promise.reject(error),
    );

    return () => {
      api.interceptors.response.eject(responseInterceptor);
      api.interceptors.request.eject(requestInterceptor);
      unregister();
    };
  }, [accessToken, customHeaders]);

  /* =========================================================
     HELPERS
  ========================================================= */

  function checkErrorCount(): boolean {
    if (isLoginPage) return false;

    setAuthenticationErrorCount(authenticationErrorCount + 1);

    if (authenticationErrorCount >= 3) {
      setAuthenticationErrorCount(0);
      mutationLogout();
      return false;
    }

    return true;
  }

  async function tryToRenewAccessToken(error: AxiosError) {
    return new Promise<void>((resolve, reject) => {
      mutationRenewAccessToken(undefined, {
        onSuccess: async () => {
          setAuthenticationErrorCount(0);
          try {
            await remakeRequest(error);
            resolve();
          } catch (e) {
            console.error("Retry request failed:", e);
            reject(e);
          }
        },
        onError: (e) => {
          console.error("Token refresh failed:", e);
          mutationLogout();
          reject(e);
        },
      });
    });
  }

  async function clearBuildVerticesState(error: AxiosError) {
    if (error?.response?.status === 500) {
      const store = useFlowStore.getState();
      store.updateBuildStatus(
        store.verticesBuild?.verticesIds ?? [],
        BuildStatus.BUILT,
      );
      store.setIsBuilding(false);
    }
  }

  async function remakeRequest(error: AxiosError) {
    const originalRequest = error.config as AxiosRequestConfig;

    try {
      const token = customGetAccessToken();
      if (!token) throw new Error("No access token");

      originalRequest.headers = {
        ...(originalRequest.headers as Record<string, string>),
        Authorization: `Bearer ${token}`,
      };

      const response = await axios.request(originalRequest);
      return response.data;
    } catch (err) {
      console.error("Remake request error:", err);
      throw err; // 🔥 controlled throw
    }
  }

  return null;
}

/* =========================================================
   HELPERS
========================================================= */

const isAuthorizedURL = (url?: string) => {
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

/* =========================================================
   STREAMING (UNCHANGED)
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

async function performStreamingRequest({
  method,
  url,
  onData,
  body,
  onError,
  onNetworkError,
  buildController,
}: StreamingRequestParams) {
  try {
    const response = await fetch(url, {
      method,
      body: body ? JSON.stringify(body) : undefined,
      signal: buildController.signal,
      headers: {
        "Content-Type": "application/json",
        Connection: "close",
      },
    });

    if (!response.ok) {
      onError?.(response.status);
      return;
    }

    if (!response.body) return;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value);
      if (await onData(JSON.parse(buffer)) === false) {
        buildController.abort();
        return;
      }
    }
  } catch (e: any) {
    onNetworkError?.(e);
  }
}

export { api, ApiInterceptor, performStreamingRequest };
