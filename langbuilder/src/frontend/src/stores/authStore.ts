import { Cookies } from "react-cookie";
import { create } from "zustand";
import {
  LANGBUILDER_ACCESS_TOKEN,
  LANGBUILDER_API_TOKEN,
} from "@/constants/constants";
import type { AuthStoreType } from "@/types/zustand/auth";

const cookies = new Cookies();

const useAuthStore = create<AuthStoreType>((set) => ({
  // auth
  isAuthenticated: !!cookies.get(LANGBUILDER_ACCESS_TOKEN),
  accessToken: cookies.get(LANGBUILDER_ACCESS_TOKEN) ?? null,
  apiKey: cookies.get(LANGBUILDER_API_TOKEN),
  authenticationErrorCount: 0,

  // authz
  role: null,
  permissions: [],

  userData: null,

  // 🔥 single entry point from backend
  setAuthContext: ({ role, permissions }) =>
    set({
      role,
      permissions,
    }),

  setIsAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
  setAccessToken: (accessToken) => set({ accessToken }),
  setUserData: (userData) => set({ userData }),
  setApiKey: (apiKey) => set({ apiKey }),
  setAuthenticationErrorCount: (authenticationErrorCount) =>
    set({ authenticationErrorCount }),

  logout: async () => {
    set({
      isAuthenticated: false,
      accessToken: null,
      apiKey: null,
      role: null,
      permissions: [],
      userData: null,
    });
  },
}));

export default useAuthStore;
