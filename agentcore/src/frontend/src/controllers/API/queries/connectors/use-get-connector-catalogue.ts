import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ConnectorInfo {
  id: string;
  name: string;
  description: string;
  provider: string;
  host: string;
  port: number;
  database_name: string;
  schema_name: string;
  username: string;
  ssl_enabled: boolean;
  status: "connected" | "disconnected" | "error";
  tables_metadata: any[] | null;
  last_tested_at: string | null;
  isCustom: boolean;
  org_id?: string | null;
  dept_id?: string | null;
}

export const useGetConnectorCatalogue: useQueryFunctionType<
  undefined,
  ConnectorInfo[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getConnectorCatalogueFn = async (): Promise<ConnectorInfo[]> => {
    const res = await api.get(`${getURL("CONNECTOR_CATALOGUE")}/`);
    return res.data ?? [];
  };

  const queryResult: UseQueryResult<ConnectorInfo[], any> = query(
    ["useGetConnectorCatalogue"],
    getConnectorCatalogueFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
