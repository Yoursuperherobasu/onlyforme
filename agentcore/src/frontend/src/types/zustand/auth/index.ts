export interface AuthStoreType {
  // 🔐 Auth
  isAuthenticated: boolean;
  accessToken: string | null;
  apiKey: string | null;
  authenticationErrorCount: number;
  autoLogin: boolean | undefined;

  // 🧑‍💻 Authorization
  role: string | null;
  permissions: string[];

  userData: Users | null;

  // 🧠 hydration flag (NEW)
  isAuthHydrated: boolean;

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
  setAuthHydrated: (value: boolean) => void;
  setAutoLogin: (autoLogin: boolean) => void;

  logout: () => Promise<void>;
}
