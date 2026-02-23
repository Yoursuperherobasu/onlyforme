import type { UseQueryOptions } from "@tanstack/react-query";
import { AxiosError } from "axios";
import buildQueryStringUrl from "@/controllers/utils/create-query-param-string";
import useAlertStore from "@/stores/alertStore";
import useAgentsManagerStore from "@/stores/agentsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import type { useQueryFunctionType } from "@/types/api";
import type { AgentType, PaginatedAgentsType } from "@/types/agent";
import {
  extractSecretFieldsFromComponents,
  processAgents,
} from "@/utils/reactFlowUtils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetAgentsParams {
  components_only?: boolean;
  get_all?: boolean;
  header_agents?: boolean;
  project_id?: string;
  remove_example_agents?: boolean;
  page?: number;
  size?: number;
}

const addQueryParams = (url: string, params: GetAgentsParams): string => {
  return buildQueryStringUrl(url, params);
};

export const useGetRefreshAgentsQuery: useQueryFunctionType<
  GetAgentsParams,
  AgentType[] | PaginatedAgentsType
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const setAgents = useAgentsManagerStore((state) => state.setAgents);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const getAgentsFn = async (
    params: GetAgentsParams,
  ): Promise<AgentType[] | PaginatedAgentsType> => {
    try {
      const url = addQueryParams(`${getURL("AGENTS")}/`, params);
      const { data: dbDataAgents } = await api.get<AgentType[]>(url);

      if (params.components_only) {
        return dbDataAgents;
      }

      const { data: dbDataComponents } = await api.get<AgentType[]>(
        addQueryParams(`${getURL("AGENTS")}/`, {
          components_only: true,
          get_all: true,
        }),
      );

      if (dbDataComponents) {
        const { data } = processAgents(dbDataComponents);
        useTypesStore.setState((state) => ({
          data: { ...state.data, ["saved_components"]: data },
          ComponentFields: extractSecretFieldsFromComponents({
            ...state.data,
            ["saved_components"]: data,
          }),
        }));
      }

      if (dbDataAgents) {
        const agents = Array.isArray(dbDataAgents)
          ? dbDataAgents
          : (dbDataAgents as { items: AgentType[] }).items;
        setAgents(agents);
        return agents;
      }

      return [];
    } catch (e) {
      if (e instanceof AxiosError && e.status !== 403) {
        setErrorData({
          title: "Could not load agents from database",
        });
      }
      throw e;
    }
  };

  const queryResult = query(
    ["useGetRefreshAgentsQuery", params],
    () => getAgentsFn(params || {}),
    options as UseQueryOptions,
  );

  return queryResult;
};
