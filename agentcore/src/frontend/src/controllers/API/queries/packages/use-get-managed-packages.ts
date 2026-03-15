import type { UseQueryResult } from "@tanstack/react-query";
import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type ManagedPackage = {
  id: string;
  name: string;
  service_name: string;
  version_spec: string;
  resolved_version: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  source: Record<string, unknown>;
};

export type GetManagedPackagesParams = {
  include_history?: boolean;
  service?: string;
};

export const useGetManagedPackages: useQueryFunctionType<
  GetManagedPackagesParams,
  ManagedPackage[]
> = (params, options?) => {
  const { query } = UseRequestProcessor();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const includeHistory = params?.include_history ?? false;
  const service = params?.service ?? "all";

  const getManagedPackagesFn = async (): Promise<ManagedPackage[]> => {
    if (!isAuthenticated) return [];
    const res = await api.get(`${getURL("PACKAGES")}/managed`, {
      params: {
        include_history: includeHistory,
        service,
      },
    });
    return res.data;
  };

  const queryResult: UseQueryResult<ManagedPackage[], any> = query(
    ["useGetManagedPackages", includeHistory, service],
    getManagedPackagesFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
