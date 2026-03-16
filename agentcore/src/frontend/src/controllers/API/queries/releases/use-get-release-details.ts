import type { UseQueryResult } from "@tanstack/react-query";
import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type ReleaseDetailRecord = {
  id: string;
  release_id: string;
  section_no: number | null;
  section_title: string | null;
  module: string | null;
  sub_module: string | null;
  feature_capability: string;
  description_details: string | null;
  sort_order: number;
  created_at: string;
};

export const useGetReleaseDetails: useQueryFunctionType<
  { releaseId: string },
  ReleaseDetailRecord[]
> = (params, options?) => {
  const { query } = UseRequestProcessor();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const getReleaseDetailsFn = async (): Promise<ReleaseDetailRecord[]> => {
    if (!isAuthenticated || !params?.releaseId) return [];
    const res = await api.get(
      `${getURL("RELEASES")}/${params.releaseId}/details`,
    );
    return res.data;
  };

  const queryResult: UseQueryResult<ReleaseDetailRecord[], any> = query(
    ["useGetReleaseDetails", params?.releaseId],
    getReleaseDetailsFn,
    {
      enabled: Boolean(params?.releaseId) && isAuthenticated,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
