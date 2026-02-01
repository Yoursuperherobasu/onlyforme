import { createContext, useEffect, useState } from "react";
import { Cookies } from "react-cookie";
import {
  LANGBUILDER_ACCESS_TOKEN,
  LANGBUILDER_API_TOKEN,
  LANGBUILDER_REFRESH_TOKEN,
} from "@/constants/constants";
import { useGetUserData } from "@/controllers/API/queries/auth";
import { useGetGlobalVariablesMutation } from "@/controllers/API/queries/variables/use-get-mutation-global-variables";
import useAuthStore from "@/stores/authStore";
import { setLocalStorage } from "@/utils/local-storage-util";
import { getAuthCookie, setAuthCookie } from "@/utils/utils";
import { useStoreStore } from "../stores/storeStore";
import type { Users } from "../types/api";
import type { AuthContextType } from "../types/contexts/auth";

const initialValue: AuthContextType = {
  accessToken: null,
  role: null,            // Match the new type
  permissions: [],
  login: () => {},
  userData: null,
  setUserData: () => {},
  authenticationErrorCount: 0,
  setApiKey: () => {},
  apiKey: null,
  storeApiKey: () => {},
  getUser: () => {},
};

export const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }): React.ReactElement {
  const cookies = new Cookies();
  const [accessToken, setAccessToken] = useState<string | null>(
    getAuthCookie(cookies, LANGBUILDER_ACCESS_TOKEN) ?? null,
  );
  // --- ADD THESE STATES FOR RBAC ---
  const [role, setRole] = useState<string | null>(localStorage.getItem("user_role"));
  const [permissions, setPermissions] = useState<string[]>(
    JSON.parse(localStorage.getItem("user_permissions") || "[]")
  );
  // ---------------------------------
  const [userData, setUserData] = useState<Users | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(
    getAuthCookie(cookies, LANGBUILDER_API_TOKEN),
  );

  const checkHasStore = useStoreStore((state) => state.checkHasStore);
  const fetchApiData = useStoreStore((state) => state.fetchApiData);
  const setIsAuthenticated = useAuthStore((state) => state.setIsAuthenticated);

  const { mutate: mutateLoggedUser } = useGetUserData();
  const { mutate: mutateGetGlobalVariables } = useGetGlobalVariablesMutation();

  useEffect(() => {
    const storedAccessToken = getAuthCookie(cookies, LANGBUILDER_ACCESS_TOKEN);
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);

  useEffect(() => {
    const apiKey = getAuthCookie(cookies, LANGBUILDER_API_TOKEN);
    if (apiKey) {
      setApiKey(apiKey);
    }
  }, []);

  function getUser() {
    mutateLoggedUser(
      {},
      {
        onSuccess: async (user) => {
          setUserData(user);
          const isSuperUser = user!.is_superuser;
          useAuthStore.getState().setIsAdmin(isSuperUser);
          checkHasStore();
          fetchApiData();
        },
        onError: () => {
          setUserData(null);
        },
      },
    );
  }

  function login(
    newAccessToken: string,
    userRole: string,        
    userPermissions: string[],
    refreshToken?: string,
    
  ) {
    setAuthCookie(cookies, LANGBUILDER_ACCESS_TOKEN, newAccessToken);
    setLocalStorage(LANGBUILDER_ACCESS_TOKEN, newAccessToken);

    if (refreshToken) {
      setAuthCookie(cookies, LANGBUILDER_REFRESH_TOKEN, refreshToken);
    }

    setLocalStorage("user_role", userRole);
    setLocalStorage("user_permissions", JSON.stringify(userPermissions));

    setRole(userRole);
    setPermissions(userPermissions);

    setAccessToken(newAccessToken);
    setIsAuthenticated(true);
    getUser();
    getGlobalVariables();
  }

  function storeApiKey(apikey: string) {
    setApiKey(apikey);
  }

  function getGlobalVariables() {
    mutateGetGlobalVariables({});
  }

  return (
    // !! to convert string to boolean
    <AuthContext.Provider
      value={{
        accessToken,
        role,          
        permissions,
        login,
        setUserData,
        userData,
        authenticationErrorCount: 0,
        setApiKey,
        apiKey,
        storeApiKey,
        getUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}