import type { Users } from "@/types/api";

export interface AuthStoreType {
  // 🔐 Auth
  isAuthenticated: boolean;
  accessToken: string | null;
  apiKey: string | null;
  authenticationErrorCount: number;

  // 🧑‍💻 Authorization (SCALABLE)
  role: string | null;
  permissions: string[];

  userData: Users | null;




  // setters
  setAuthContext: (payload: {
    role: string;
    permissions: string[];
  }) => void;

  setIsAuthenticated: (isAuthenticated: boolean) => void;
  setAccessToken: (accessToken: string | null) => void;
  setUserData: (userData: Users | null) => void;
  setApiKey: (apiKey: string | null) => void;
  setAuthenticationErrorCount: (authenticationErrorCount: number) => void;

  logout: () => Promise<void>;
}
