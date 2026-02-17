import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { AuthSettingsType, MCPSettingsType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchAgentMCPParams {
  project_id: string;
}

interface PatchAgentMCPRequest {
  settings: MCPSettingsType[];
  auth_settings?: AuthSettingsType;
}

interface PatchAgentMCPResponse {
  message: string;
  result?: {
    project_id: string;
    sse_url?: string;
    uses_composer: boolean;
    error_message?: string;
  };
}

export const usePatchAgentsMCP: useMutationFunctionType<
  PatchAgentMCPParams,
  PatchAgentMCPRequest,
  PatchAgentMCPResponse
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchAgentMCP(
    requestData: PatchAgentMCPRequest,
  ): Promise<PatchAgentMCPResponse> {
    const res = await api.patch(
      `${getURL("MCP")}/${params.project_id}`,
      requestData,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    PatchAgentMCPResponse,
    any,
    PatchAgentMCPRequest
  > = mutate(["usePatchAgentsMCP"], patchAgentMCP, {
    onSuccess: (data, variables, context) => {
      const authSettings = (variables as unknown as PatchAgentMCPRequest)
        .auth_settings;
      // Update the auth settings cache immediately to prevent race conditions
      const currentMCPData = queryClient.getQueryData([
        "useGetAgentsMCP",
        params.project_id,
      ]);
      if (currentMCPData && authSettings !== undefined) {
        queryClient.setQueryData(["useGetAgentsMCP", params.project_id], {
          ...currentMCPData,
          auth_settings: authSettings,
        });
      }

      // Always invalidate the composer URL cache when auth settings change
      // This ensures the query re-runs with the new auth state
      queryClient.invalidateQueries({
        queryKey: ["project-composer-url", params.project_id],
      });

      // Call the original onSuccess if provided
      if (options?.onSuccess) {
        options.onSuccess(data, variables, context);
      }
    },
    onSettled: () => {
      // Use invalidateQueries instead of refetchQueries to avoid race conditions
      // This marks the queries as stale but doesn't immediately refetch them
      queryClient.invalidateQueries({ queryKey: ["useGetAgentsMCP"] });
    },
    ...options,
  });

  return mutation;
};
