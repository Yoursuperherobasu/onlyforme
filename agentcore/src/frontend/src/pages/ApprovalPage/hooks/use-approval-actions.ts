import { useCallback } from "react";
import {
  useApproveAgent,
  useRejectAgent,
} from "@/controllers/API/queries/approvals";
import useAlertStore from "@/stores/alertStore";
import type { ApprovalAgent } from "@/controllers/API/queries/approvals";

/**
 * Custom hook to handle approval and rejection actions
 * Combines API mutations and user feedback notifications
 */
export const useApprovalActions = () => {
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  // API mutation hooks
  const approveAgentMutation = useApproveAgent();
  const rejectAgentMutation = useRejectAgent();

  /**
   * Handle agent approval
   * Sends comments + attachments in one approve request
   */
  const handleApprove = useCallback(
    async (
      agent: ApprovalAgent,
      comments: string,
      attachments: File[],
    ) => {
      try {
        const entityLabel = agent.entityType === "mcp" ? "MCP request" : "Agent";
        await new Promise((resolve, reject) => {
          approveAgentMutation.mutate(
            {
              agentId: agent.id,
              comments,
              attachments,
            },
            {
              onSuccess: () => {
                setSuccessData({
                  title: `${entityLabel} "${agent.title}" approved successfully.`,
                });
                resolve(null);
              },
              onError: () => {
                setErrorData({
                  title: `Failed to approve ${entityLabel.toLowerCase()} "${agent.title}".`,
                });
                reject(new Error("Approval failed"));
              },
            },
          );
        });
      } catch (error) {
        console.error("Approval error:", error);
      }
    },
    [approveAgentMutation, setSuccessData, setErrorData],
  );

  /**
   * Handle agent rejection
   * Sends comments + attachments in one reject request
   */
  const handleReject = useCallback(
    async (
      agent: ApprovalAgent,
      comments: string,
      attachments: File[],
    ) => {
      try {
        const entityLabel = agent.entityType === "mcp" ? "MCP request" : "Agent";
        await new Promise((resolve, reject) => {
          rejectAgentMutation.mutate(
            {
              agentId: agent.id,
              comments,
              attachments,
            },
            {
              onSuccess: () => {
                setSuccessData({
                  title: `${entityLabel} "${agent.title}" rejected.`,
                });
                resolve(null);
              },
              onError: () => {
                setErrorData({
                  title: `Failed to reject ${entityLabel.toLowerCase()} "${agent.title}".`,
                });
                reject(new Error("Rejection failed"));
              },
            },
          );
        });
      } catch (error) {
        console.error("Rejection error:", error);
      }
    },
    [rejectAgentMutation, setSuccessData, setErrorData],
  );

  return {
    handleApprove,
    handleReject,
    isLoading:
      approveAgentMutation.isPending ||
      rejectAgentMutation.isPending,
  };
};
