import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import type { ModelType } from "@/types/models/models";

export const useGetRegistryModels = (params?: {
  provider?: string;
  environment?: string;
  active_only?: boolean;
}) => {
  return useQuery<ModelType[]>({
    queryKey: ["registry-models", params],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (params?.provider) searchParams.set("provider", params.provider);
      if (params?.environment)
        searchParams.set("environment", params.environment);
      if (params?.active_only !== undefined)
        searchParams.set("active_only", String(params.active_only));

      const qs = searchParams.toString();
      const url = `api/models/registry/${qs ? `?${qs}` : ""}`;
      const response = await api.get(url);
      return response.data;
    },
    refetchOnMount: true,
  });
};