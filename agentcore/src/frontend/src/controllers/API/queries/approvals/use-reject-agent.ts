import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface RejectAgentParams {
  agentId: string;
  comments: string;
  reason?: string;
}

/**
 * Hook to reject an agent
 * Sends rejection request with comments and optional reason to the backend
 */
export const useRejectAgent: useMutationFunctionType<
  undefined,
  RejectAgentParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const rejectAgentFn = async (
    params: RejectAgentParams,
  ): Promise<void> => {
    const payload = {
      comments: params.comments,
      reason: params.reason || "Not approved",
    };

    await api.post(
      `${getURL("APPROVALS")}/${params.agentId}/reject`,
      payload,
    );
  };

  const mutation: UseMutationResult<
    void,
    any,
    RejectAgentParams
  > = mutate(["useRejectAgent"], rejectAgentFn, {
    ...options,
    onSettled: () => {
      // Refetch approvals list after rejection
      queryClient.refetchQueries({ queryKey: ["useGetApprovals"] });
    },
  });

  return mutation;
};
