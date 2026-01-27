import * as Form from "@radix-ui/react-form";
import { useContext, useState } from "react";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { Button } from "../../components/ui/button";
import { SIGNIN_ERROR_ALERT } from "../../constants/alerts_constants";
import { CONTROL_LOGIN_STATE } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import type { LoginType } from "../../types/api";
import type {
  inputHandlerEventType,
  loginInputStateType,
} from "../../types/components";

import { useMsal } from "@azure/msal-react";
import { loginRequest } from "@/authConfig";
import { useTranslation } from "react-i18next";
import useAuthStore from "@/stores/authStore";

import MothersonLogo from "@/assets/mothersonLogo.svg?react";
import { DotPattern } from "./components/DotPattern";
import { Starfield } from "./components/StarField";

export default function LoginPage(): JSX.Element {
  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);

  const { password, username } = inputState;

  // legacy auth context (tokens / redirect)
  const { login } = useContext(AuthContext);

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { instance } = useMsal();
  const { t } = useTranslation();

  // 🔥 ZUSTAND (REACTIVE)
  const setAuthContext = useAuthStore((s) => s.setAuthContext);
  const setIsAuthenticated = useAuthStore((s) => s.setIsAuthenticated);

  const { mutate } = useLoginUser();

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  /* =========================
     AZURE SSO LOGIN
     ========================= */
  async function handleAzureSSO() {
    try {
      console.log("🟣 [SSO] Starting Azure login...");

      const response = await instance.loginPopup(loginRequest);
      console.log("🟣 [SSO] Azure popup success:", response);

      const idToken = response.idToken;

      console.log("🟣 [SSO] Sending token to backend...");

      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/api/v1/azure/sso`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ idToken }),
        },
      );

      if (!res.ok) {
        const text = await res.text();
        console.error("🔴 [SSO] Backend error:", text);
        throw new Error(text || "Backend SSO failed");
      }

      const data = await res.json();

      console.log("✅ [SSO] BACKEND TOKEN RESPONSE:", data);

      // legacy token handling (cookies, redirects)
      console.log("🟡 [SSO] Calling AuthContext.login()");
      setAuthContext({
        role: data.role,
        permissions: data.permissions,
      });
      setIsAuthenticated(true);

      console.log("🟢 [SSO] Zustand AFTER SET:", useAuthStore.getState());

      // optional redirect
      // window.location.href = "/";
    } catch (err) {
      console.error("🔴 [SSO] Azure SSO failed:", err);
    }
  }

  /* =========================
     USERNAME / PASSWORD LOGIN
     ========================= */
  function signIn() {
    const user: LoginType = {
      username: username.trim(),
      password: password.trim(),
    };

    console.log("🟣 [LOGIN] Starting username/password login...");

    mutate(user, {
      onSuccess: (data) => {
        console.log("✅ [LOGIN] BACKEND TOKEN RESPONSE:", data);

        console.log("🟡 [LOGIN] Calling AuthContext.login()");
        login(
          data.access_token,
          data.role,
          data.permissions,
          data.refresh_token,
        );

        console.log("🟢 [LOGIN] Updating Zustand auth store...");
        setAuthContext({
          role: data.role,
          permissions: data.permissions,
        });
        setIsAuthenticated(true);

        console.log("🟢 [LOGIN] Zustand AFTER SET:", useAuthStore.getState());
      },
      onError: (error) => {
        console.error("🔴 [LOGIN] Login failed:", error);
        setErrorData({
          title: SIGNIN_ERROR_ALERT,
          list: [error["response"]["data"]["detail"]],
        });
      },
    });
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white overflow-hidden relative">
      <DotPattern />
      <Starfield />

      <div className="relative z-10 min-h-screen flex flex-col lg:flex-row">
        {/* LEFT */}
        <div className="flex-1 flex flex-col justify-center px-6 sm:px-12 lg:px-16 xl:px-24 py-12 lg:py-0">
          <div className="mb-4">
            <MothersonLogo className="h-10 sm:h-12 w-auto" />
          </div>

          <div className="max-w-md">
            <h1 className="text-3xl sm:text-4xl lg:text-5xl mb-4 font-bold">
              {t("Build AI Agents, faster.")}
            </h1>
            <p className="text-gray-400 text-base sm:text-lg">
              {t(
                "Connect your ideas to reality with AgentCore's powerful platform.",
              )}
            </p>
          </div>
        </div>

        {/* RIGHT */}
        <div className="flex-1 flex items-center justify-center px-6 sm:px-12 lg:px-16 py-12 lg:py-0">
          <div className="w-full max-w-md">
            <div className="mb-8">
              <h2 className="text-2xl sm:text-3xl mb-2 font-semibold">
                {t("Welcome back.")}
              </h2>
              <p className="text-gray-400 text-sm sm:text-base">
                {t(
                  "Sign in to your account to continue building intelligent agents.",
                )}
              </p>
            </div>

            <Form.Root
              onSubmit={(event) => {
                event.preventDefault();
                if (password !== "") signIn();
              }}
              className="space-y-4"
            >
              <div className="grid grid-cols-2 gap-3">
                <Button
                  type="button"
                  onClick={handleAzureSSO}
                  className="h-12 bg-[#9810FA] hover:bg-[#8a0ee0] text-white flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" viewBox="0 0 23 23">
                    <path fill="#f25022" d="M1 1h10v10H1z" />
                    <path fill="#7fba00" d="M12 1h10v10H12z" />
                    <path fill="#00a4ef" d="M1 12h10v10H1z" />
                    <path fill="#ffb900" d="M12 12h10v10H12z" />
                  </svg>
                  {t("SSO")}
                </Button>
              </div>
            </Form.Root>
          </div>
        </div>
      </div>
    </div>
  );
}
