import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useGetTypes } from "@/controllers/API/queries/agents/use-get-types";
import { useGetApprovalPreview } from "@/controllers/API/queries/approvals";
import CustomLoader from "@/customization/components/custom-loader";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAgentsManagerStore from "@/stores/agentsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import Page from "../AgentBuilderPage/components/PageComponent";

export default function ApprovalPreviewPage(): JSX.Element {
  const navigate = useCustomNavigate();
  const { agentId } = useParams();
  const types = useTypesStore((state) => state.types);
  const setCurrentAgent = useAgentsManagerStore((state) => state.setCurrentAgent);

  useGetTypes({
    enabled: Object.keys(types).length <= 0,
  });

  const {
    data: previewAgent,
    isLoading,
    isError,
  } = useGetApprovalPreview(
    { agent_id: agentId || "" },
    { enabled: !!agentId },
  );

  useEffect(() => {
    if (previewAgent) {
      setCurrentAgent(previewAgent);
    }
    return () => {
      setCurrentAgent(undefined);
    };
  }, [previewAgent, setCurrentAgent]);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold">
            {previewAgent?.name || "Review Details"}
          </h1>
          <p className="text-xs text-muted-foreground">
            Read-only flow preview
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate("/approval")}>
          Back to Approval
        </Button>
      </div>
      <div className="h-full w-full">
        {isLoading ? (
          <div className="flex h-full w-full items-center justify-center">
            <CustomLoader />
          </div>
        ) : !previewAgent || isError ? (
          <div className="flex h-full w-full items-center justify-center p-6">
            <div className="rounded-lg border border-border bg-card p-6 text-center">
              <p className="text-sm text-muted-foreground">
                Unable to load review preview for this approval.
              </p>
            </div>
          </div>
        ) : (
          <Page
            view
            enableViewportInteractions
            setIsLoading={() => undefined}
          />
        )}
      </div>
    </div>
  );
}
