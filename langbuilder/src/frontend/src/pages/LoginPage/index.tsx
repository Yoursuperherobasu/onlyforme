import * as Form from "@radix-ui/react-form";
import { useContext, useState } from "react";
import { Mail, Lock } from "lucide-react";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import InputComponent from "../../components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { SIGNIN_ERROR_ALERT } from "../../constants/alerts_constants";
import { CONTROL_LOGIN_STATE } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import type { LoginType } from "../../types/api";
import MothersonLogo from "@/assets/mothersonLogo.svg?react";
import type {
  inputHandlerEventType,
  loginInputStateType,
} from "../../types/components";
import { DotPattern } from "./components/DotPattern";
import { Starfield } from "./components/StarField";

import { useMsal } from "@azure/msal-react";
import { loginRequest } from "@/authConfig";

export default function LoginPage(): JSX.Element {
  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);

  const { password, username } = inputState;
  const { login } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { instance } = useMsal();


  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  const { mutate } = useLoginUser();


  async function handleAzureSSO() {
  try {
    // Open Microsoft login popup using your msalConfig + loginRequest
    const response = await instance.loginPopup(loginRequest);

    console.log("Azure login success:", response);

    const idToken = response.idToken;
    
    // Send token to LangBuilder backend
    const res = await fetch(
  `${import.meta.env.VITE_API_URL}/api/v1/azure/sso`,
  {
    method: "POST",
    credentials: "include",   // VERY IMPORTANT
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken }),
  }
);




    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || "Backend SSO failed");
    }

    const data = await res.json();

    // Login user in your app
    console.log("BACKEND TOKEN RESPONSE:", data);
    login(data.access_token,  data.role, data.permissions, data.refresh_token);
  //  setTimeout(() => window.location.href = "/", 50);
  } catch (err) {
    console.error("Azure SSO failed:", err);
  }
}


  function signIn() {
    const user: LoginType = {
      username: username.trim(),
      password: password.trim(),
    };

    mutate(user, {
      onSuccess: (data) => {
        console.log(  "Login successful, data:", data);
        login(data.access_token,  data.role, data.permissions, data.refresh_token);
      },
      onError: (error) => {
        setErrorData({
          title: SIGNIN_ERROR_ALERT,
          list: [error["response"]["data"]["detail"]],
        });
      },
    });
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white overflow-hidden relative">
      {/* Dotted Background Pattern */}
      <DotPattern />

      {/* Animated Starfield Background */}
      <Starfield />

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex flex-col lg:flex-row">
        {/* Left Side - Branding */}
        <div className="flex-1 flex flex-col justify-center px-6 sm:px-12 lg:px-16 xl:px-24 py-12 lg:py-0">
          {/* Logo */}
          <div className="mb-3 lg:mb-4">
            <div className="mb-3 lg:mb-4">
              <MothersonLogo className="h-10 sm:h-12 w-auto" />
            </div>
          </div>

          {/* Heading */}
          <div className="max-w-md">
            <h1 className="text-3xl sm:text-4xl lg:text-5xl mb-4 sm:mb-6 font-bold">
              Build AI Agents, faster.
            </h1>
            <p className="text-gray-400 text-base sm:text-lg">
              Connect your ideas to reality with AgentCore's powerful platform.
            </p>
          </div>
        </div>

        {/* Right Side - Login Form */}
        <div className="flex-1 flex items-center justify-center px-6 sm:px-12 lg:px-16 py-12 lg:py-0">
          <div className="w-full max-w-md">
            {/* Welcome Text */}
            <div className="mb-8">
              <h2 className="text-2xl sm:text-3xl mb-2 font-semibold">
                Welcome back.
              </h2>
              <p className="text-gray-400 text-sm sm:text-base">
                Sign in to your AgentCore account to continue.
              </p>
            </div>

            {/* Login Form */}
            <Form.Root
              onSubmit={(event) => {
                if (password === "") {
                  event.preventDefault();
                  return;
                }
                signIn();
                const _data = Object.fromEntries(
                  new FormData(event.currentTarget)
                );
                event.preventDefault();
              }}
              className="space-y-4"
            >
              {/* Username Input */}
              <div>
                <Form.Field name="username">
                  <div className="relative w-full">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 z-10 pointer-events-none" />
                    <Form.Control asChild>
                      <Input
                        type="text"
                        onChange={({ target: { value } }) => {
                          handleInput({ target: { name: "username", value } });
                        }}
                        value={username}
                        className="w-full pl-14 pr-4 h-14 bg-[#1a1a1a] border border-gray-700 rounded-lg text-white placeholder:text-gray-500 focus:border-purple-500 focus:ring-1 focus:ring-purple-500/20"
                        required
                        placeholder="Username"
                      />
                    </Form.Control>
                  </div>
                  <Form.Message
                    match="valueMissing"
                    className="text-sm text-red-400 mt-1"
                  >
                    Please enter your username
                  </Form.Message>
                </Form.Field>
              </div>
              {/* Password Input */}
              <div>
                <Form.Field name="password">
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 z-10" />
                    <InputComponent
                      onChange={(value) => {
                        handleInput({ target: { name: "password", value } });
                      }}
                      value={password}
                      isForm
                      password={true}
                      required
                      placeholder="Password"
                      className="w-full pl-11 h-12 bg-[#1a1a1a] border-gray-700 text-white placeholder:text-gray-500 focus:border-purple-500 focus:ring-purple-500/20"
                    />
                  </div>
                  <Form.Message
                    className="text-sm text-red-400 mt-1"
                    match="valueMissing"
                  >
                    Please enter your password
                  </Form.Message>
                </Form.Field>
              </div>

              {/* Sign In Button */}
              <div className="grid grid-cols-2 gap-3">
                {/* Normal Sign In */}
                <Form.Submit asChild>
                  <Button
                    type="submit"
                    className="h-12 bg-purple-600 hover:bg-purple-700 text-white text-base font-medium"
                  >
                    Sign In
                  </Button>
                </Form.Submit>

                {/* Azure SSO */}
                <Button
                  type="button"
                  onClick={handleAzureSSO}
                  className="h-12 bg-[#2f2f2f] hover:bg-[#3a3a3a] text-white text-base font-medium flex items-center justify-center gap-2"
                >
                  <svg className="w-5 h-5" viewBox="0 0 23 23">
                    <path fill="#f25022" d="M1 1h10v10H1z" />
                    <path fill="#7fba00" d="M12 1h10v10H12z" />
                    <path fill="#00a4ef" d="M1 12h10v10H1z" />
                    <path fill="#ffb900" d="M12 12h10v10H12z" />
                  </svg>
                  SSO
                </Button>
              </div>

              {/* Sign Up Link */}
              <div className="text-center pt-2">
                <p className="text-sm text-gray-400">
                  New to AgentCore?{" "}
                  <CustomLink
                    to="/signup"
                    className="text-purple-500 hover:text-purple-400 font-medium"
                  >
                    Create an account
                  </CustomLink>
                </p>
              </div>
            </Form.Root>
          </div>
        </div>
      </div>
    </div>
  );
}
