import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface HITLRequestItem {
  id: string;
  thread_id: string;
  agent_id: string;
  agent_name: string | null;
  session_id: string | null;
  interrupt_data: {
    question: string;
    context: string;
    actions: string[];
    timeout_seconds: number;
  } | null;
  status:
    | "pending"
    | "approved"
    | "rejected"
    | "edited"
    | "cancelled"
    | "timed_out";
  decision: {
    action: string;
    feedback: string;
    edited_value: string;
  } | null;
  requested_at: string;
  decided_at: string | null;
}

interface GetHitlPendingParams {
  status?: string;
}

/**
 * Hook to fetch HITL (Human-in-the-Loop) requests.
 *
 * @param params.status  "pending" (default) — only pending requests
 *                       "all"               — all requests including history
 *
 * Auto-refreshes every 15 seconds so new paused runs appear without manual reload.
 */
export const useGetHitlPending: useQueryFunctionType<
  GetHitlPendingParams,
  HITLRequestItem[]
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getHitlFn = async (): Promise<HITLRequestItem[]> => {
    const url =
      params?.status === "all"
        ? `${getURL("HITL")}/pending?status=all`
        : `${getURL("HITL")}/pending`;
    const res = await api.get<HITLRequestItem[]>(url);
    return res.data;
  };

  return query(
    ["useGetHitlPending", params?.status ?? "pending"],
    getHitlFn,
    {
      refetchInterval: 15000,
      ...options,
    },
  );
};
