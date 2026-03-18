import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { TagItem } from "./use-get-predefined-tags";

export const useGetPopularTags: useQueryFunctionType<
  undefined,
  TagItem[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    const { data } = await api.get<TagItem[]>(
      `${getURL("TAGS")}/popular?limit=15`,
    );
    return data;
  };

  return query(["useGetPopularTags"], responseFn, {
    refetchOnWindowFocus: false,
    staleTime: 60 * 1000,
    ...options,
  });
};
