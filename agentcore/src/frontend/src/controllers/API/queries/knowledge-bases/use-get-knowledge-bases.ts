import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface KnowledgeBaseInfo {
  id: string;
  name: string;
  org_id?: string | null;
  dept_id?: string | null;
  embedding_provider?: string;
  embedding_model?: string;
  size: number;
  words: number;
  characters: number;
  chunks: number;
  avg_chunk_size: number;
  file_count?: number;
}

export const useGetKnowledgeBases: useQueryFunctionType<
  undefined,
  KnowledgeBaseInfo[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getKnowledgeBasesFn = async (): Promise<KnowledgeBaseInfo[]> => {
    const res = await api.get(`${getURL("KNOWLEDGE_BASES")}/`);
    return res.data;
  };

  const queryResult: UseQueryResult<KnowledgeBaseInfo[], any> = query(
    ["useGetKnowledgeBases"],
    getKnowledgeBasesFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
