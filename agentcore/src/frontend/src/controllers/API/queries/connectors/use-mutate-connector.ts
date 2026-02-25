import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface CreateConnectorPayload {
  name: string;
  description?: string;
  provider: string;
  // DB provider fields (optional for non-DB providers)
  host?: string | null;
  port?: number | null;
  database_name?: string | null;
  schema_name?: string | null;
  username?: string | null;
  password?: string | null;
  ssl_enabled?: boolean;
  // Non-DB provider config (Azure Blob, SharePoint)
  provider_config?: Record<string, any> | null;
  org_id?: string | null;
  dept_id?: string | null;
}

export interface UpdateConnectorPayload extends Partial<CreateConnectorPayload> {}

export const useCreateConnector = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateConnectorPayload) => {
      const res = await api.post(`${getURL("CONNECTOR_CATALOGUE")}/`, payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetConnectorCatalogue"] });
    },
  });
};

export const useUpdateConnector = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: string;
      payload: UpdateConnectorPayload;
    }) => {
      const res = await api.patch(
        `${getURL("CONNECTOR_CATALOGUE")}/${id}`,
        payload,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetConnectorCatalogue"] });
    },
  });
};

export const useDeleteConnector = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.delete(`${getURL("CONNECTOR_CATALOGUE")}/${id}`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetConnectorCatalogue"] });
    },
  });
};

export const useTestConnectorConnection = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(
        `${getURL("CONNECTOR_CATALOGUE")}/${id}/test-connection`,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetConnectorCatalogue"] });
    },
  });
};

export const useDisconnectConnector = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(
        `${getURL("CONNECTOR_CATALOGUE")}/${id}/disconnect`,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetConnectorCatalogue"] });
    },
  });
};
