import { useCallback } from "react";
import {
  useApproveAgent,
  useRejectAgent,
  useUploadApprovalAttachments,
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
  const uploadAttachmentsMutation = useUploadApprovalAttachments();

  /**
   * Handle agent approval
   * Uploads attachments first (if any), then sends approval with comments
   */
  const handleApprove = useCallback(
    async (
      agent: ApprovalAgent,
      comments: string,
      attachments: File[],
    ) => {
      try {
        // Upload attachments if provided
        if (attachments.length > 0) {
          await new Promise((resolve, reject) => {
            uploadAttachmentsMutation.mutate(
              {
                agentId: agent.id,
                files: attachments,
              },
              {
                onSuccess: resolve,
                onError: reject,
              },
            );
          });
        }

        // Then approve the agent
        await new Promise((resolve, reject) => {
          approveAgentMutation.mutate(
            {
              agentId: agent.id,
              comments,
            },
            {
              onSuccess: () => {
                setSuccessData({
                  title: `Agent "${agent.title}" approved successfully.`,
                });
                resolve(null);
              },
              onError: () => {
                setErrorData({
                  title: `Failed to approve agent "${agent.title}".`,
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
    [approveAgentMutation, uploadAttachmentsMutation, setSuccessData, setErrorData],
  );

  /**
   * Handle agent rejection
   * Uploads attachments first (if any), then sends rejection with comments
   */
  const handleReject = useCallback(
    async (
      agent: ApprovalAgent,
      comments: string,
      attachments: File[],
    ) => {
      try {
        // Upload attachments if provided
        if (attachments.length > 0) {
          await new Promise((resolve, reject) => {
            uploadAttachmentsMutation.mutate(
              {
                agentId: agent.id,
                files: attachments,
              },
              {
                onSuccess: resolve,
                onError: reject,
              },
            );
          });
        }

        // Then reject the agent
        await new Promise((resolve, reject) => {
          rejectAgentMutation.mutate(
            {
              agentId: agent.id,
              comments,
            },
            {
              onSuccess: () => {
                setSuccessData({
                  title: `Agent "${agent.title}" rejected.`,
                });
                resolve(null);
              },
              onError: () => {
                setErrorData({
                  title: `Failed to reject agent "${agent.title}".`,
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
    [rejectAgentMutation, uploadAttachmentsMutation, setSuccessData, setErrorData],
  );

  return {
    handleApprove,
    handleReject,
    isLoading:
      approveAgentMutation.isPending ||
      rejectAgentMutation.isPending ||
      uploadAttachmentsMutation.isPending,
  };
};
