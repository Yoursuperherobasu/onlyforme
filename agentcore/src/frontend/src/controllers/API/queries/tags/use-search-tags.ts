import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { TagItem } from "./use-get-predefined-tags";

interface SearchTagsParams {
  q: string;
  category?: string;
  limit?: number;
}

export const useSearchTags = (params: SearchTagsParams) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.set("q", params.q);
    if (params.category) searchParams.set("category", params.category);
    if (params.limit) searchParams.set("limit", String(params.limit));

    const { data } = await api.get<TagItem[]>(
      `${getURL("TAGS")}/search?${searchParams.toString()}`,
    );
    return data;
  };

  return query(
    ["useSearchTags", params.q, params.category],
    responseFn,
    {
      refetchOnWindowFocus: false,
      enabled: params.q.length > 0,
      staleTime: 30 * 1000,
    },
  );
};
