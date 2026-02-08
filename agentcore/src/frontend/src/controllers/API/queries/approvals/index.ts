/**
 * Approvals API Query Hooks
 * 
 * This module exports all approval-related API hooks for fetching and managing agent approvals.
 * These hooks use React Query (tanstack/react-query) for caching and state management.
 */

export { useGetApprovals } from "./use-get-approvals";
export type { ApprovalAgent } from "./use-get-approvals";

export { useApproveAgent } from "./use-approve-agent";

export { useRejectAgent } from "./use-reject-agent";

export { useUploadApprovalAttachments } from "./use-upload-approval-attachments";
