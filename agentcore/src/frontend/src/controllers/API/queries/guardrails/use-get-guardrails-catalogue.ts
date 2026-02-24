import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GuardrailRuntimeConfig {
  config_yml?: string;
  rails_co?: string;
  prompts_yml?: string;
  files?: Record<string, string>;
}

export interface GuardrailInfo {
  id: string;
  name: string;
  description: string;
  provider: string;
  category: string;
  status: "active" | "inactive";
  rulesCount: number;
  isCustom: boolean;
  runtimeConfig?: GuardrailRuntimeConfig | null;
  runtimeReady?: boolean;
  org_id?: string | null;
  dept_id?: string | null;
}

export interface GuardrailCreateOrUpdatePayload {
  name: string;
  description?: string | null;
  provider: string;
  category: string;
  status: "active" | "inactive";
  rulesCount: number;
  isCustom: boolean;
  runtimeConfig?: GuardrailRuntimeConfig | null;
  org_id?: string | null;
  dept_id?: string | null;
}

export const useGetGuardrailsCatalogue: useQueryFunctionType<
  undefined,
  GuardrailInfo[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getGuardrailsCatalogueFn = async (): Promise<GuardrailInfo[]> => {
    const res = await api.get(`${getURL("GUARDRAILS_CATALOGUE")}/`);
    return res.data ?? [];
  };

  const queryResult: UseQueryResult<GuardrailInfo[], any> = query(
    ["useGetGuardrailsCatalogue"],
    getGuardrailsCatalogueFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
