import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IUnpublishFlowRequest {
  agent_id: string;
  agentcore_url: string;
  agentcore_api_key: string;
}

export interface IUnpublishFlowResponse {
  success: boolean;
  message: string;
  agent_id: string;
  platform_url: string;
}

export const useDeleteUnpublishFlow: useMutationFunctionType<
  IUnpublishFlowResponse,
  IUnpublishFlowRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const unpublishFlowFn = async (
    payload: IUnpublishFlowRequest,
  ): Promise<IUnpublishFlowResponse> => {
    const response = await api.delete<IUnpublishFlowResponse>(
      `${getURL("PUBLISH")}/agentcore`,
      {
        data: {
          agent_id: payload.agent_id,
          agentcore_url: payload.agentcore_url,
          agentcore_api_key: payload.agentcore_api_key,
        },
      },
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    IUnpublishFlowResponse,
    any,
    IUnpublishFlowRequest
  > = mutate(["useDeleteUnpublishFlow"], unpublishFlowFn, {
    ...options,
    onSettled: (response) => {
      if (response?.agent_id) {
        // Refetch publish status for this flow
        queryClient.invalidateQueries({
          queryKey: ["useGetPublishStatus", response.agent_id],
        });
      }
    },
  });

  return mutation;
};
