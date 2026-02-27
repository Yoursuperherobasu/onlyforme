import type { useQueryFunctionType } from "@/types/api";
import type { AgentType } from "@/types/agent";
import { processAgents } from "@/utils/reactFlowUtils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ApprovalPreviewResponse {
  id: string;
  title: string;
  version: string;
  snapshot: AgentType["data"];
}

interface GetApprovalPreviewParams {
  agent_id: string;
}

export const useGetApprovalPreview: useQueryFunctionType<
  GetApprovalPreviewParams,
  AgentType | null
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getApprovalPreviewFn = async (): Promise<AgentType | null> => {
    if (!params?.agent_id) return null;

    const res = await api.get<ApprovalPreviewResponse>(
      `${getURL("APPROVALS")}/${params.agent_id}/preview`,
    );

    const previewAgent: AgentType = {
      id: `approval-preview-${res.data.id}`,
      name: res.data.title,
      description: "",
      data: res.data.snapshot,
      public: true,
      locked: true,
    };

    const { agents } = processAgents([previewAgent]);
    return agents[0];
  };

  return query(
    ["useGetApprovalPreview", params?.agent_id],
    getApprovalPreviewFn,
    {
      enabled: !!params?.agent_id,
      ...options,
    },
  );
};
