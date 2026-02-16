import useAuthStore from "@/stores/authStore";
import { LoadingPage } from "@/pages/LoadingPage";
import AccessDeniedPage from "@/pages/AccessDeniedPage";

export const ProtectedAccessControlRoute = ({
  children,
}: {
  children: JSX.Element;
}) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const permissions = useAuthStore((state) => state.permissions);

  if (!isAuthenticated) {
    return <LoadingPage />;
  }

  const canAccess = permissions.includes("view_access_control_page") ||
    permissions.includes("manage_roles");

  if (!canAccess) {
    return (
      <AccessDeniedPage message="You do not have access to manage roles and permissions." />
    );
  }

  return children;
};
