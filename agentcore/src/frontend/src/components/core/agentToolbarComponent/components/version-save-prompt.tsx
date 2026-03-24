import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import useAlertStore from "@/stores/alertStore";
import useAgentStore from "@/stores/agentStore";
import useAgentsManagerStore from "@/stores/agentsManagerStore";
import useSaveAgent from "@/hooks/agents/use-save-agent";
import { useGetPublishVersions } from "@/controllers/API/queries/agents/use-get-publish-versions";
import { usePostUnifiedPublishAgent } from "@/controllers/API/queries/agents/use-post-unified-publish-agent";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

type PublishContextResponse = {
  agent_id: string;
  org_id: string;
  department_id: string;
  department_admin_id: string;
};

const parseVersionNumber = (raw: string | null | undefined): number => {
  if (!raw) return 0;
  const cleaned = String(raw).trim().replace(/^v/i, "");
  const parsed = Number.parseInt(cleaned, 10);
  return Number.isNaN(parsed) ? 0 : parsed;
};

const VersionSavePrompt = (): JSX.Element | null => {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const versionSavePrompt = useAgentsManagerStore((state) => state.versionSavePrompt);
  const clearVersionSavePrompt = useAgentsManagerStore((state) => state.clearVersionSavePrompt);
  const setAutoSaveDisabledForAgent = useAgentsManagerStore(
    (state) => state.setAutoSaveDisabledForAgent,
  );
  const setActivePublishedVersion = useAgentStore(
    (state) => state.setActivePublishedVersion,
  );
  const saveAgent = useSaveAgent();
  const publishMutation = usePostUnifiedPublishAgent();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const agentId = versionSavePrompt?.version.agentId ?? "";
  const env = versionSavePrompt?.version.environment ?? "uat";

  const { data: versions } = useGetPublishVersions(
    { agent_id: agentId, env },
    { enabled: Boolean(versionSavePrompt?.version.agentId) },
  );

  const nextVersionLabel = useMemo(() => {
    const max = Math.max(
      0,
      ...(versions ?? []).map((record) => parseVersionNumber(record.version_number)),
    );
    return `v${max + 1}`;
  }, [versions]);

  if (!versionSavePrompt) {
    return null;
  }

  const handleClose = () => {
    if (isSubmitting) return;
    clearVersionSavePrompt();
  };

  const handleCreateVersion = async () => {
    if (!agentId) {
      handleClose();
      return;
    }
    setIsSubmitting(true);
    try {
      await saveAgent(undefined, { skipVersionGuard: true });

      const contextRes = await api.get<PublishContextResponse>(
        `${getURL("PUBLISH")}/${agentId}/context`,
      );
      const context = contextRes.data;

      const response = await publishMutation.mutateAsync({
        agent_id: agentId,
        department_id: context.department_id,
        department_admin_id: context.department_admin_id,
        visibility: versionSavePrompt.version.visibility ?? "PRIVATE",
        environment: env,
      });

      setSuccessData({
        title: response.message || `Published ${response.version_number}`,
      });

      queryClient.invalidateQueries({
        queryKey: ["useGetPublishVersions", agentId, env],
      });

      setActivePublishedVersion(null);
      clearVersionSavePrompt();
    } catch (error: any) {
      setErrorData({
        title: "Failed to create new version",
        list: [
          error?.response?.data?.detail || error?.message || "Unknown error",
        ],
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDisableAutoSave = () => {
    if (agentId) {
      setAutoSaveDisabledForAgent(agentId, true);
    }
    clearVersionSavePrompt();
  };

  const isAutoPrompt = versionSavePrompt.source === "auto";
  const currentVersionLabel = versionSavePrompt.version.versionNumber;

  return (
    <Dialog open onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New version required</DialogTitle>
          <DialogDescription>
            You are editing published {currentVersionLabel}. Create a new version{" "}
            {nextVersionLabel} instead of overwriting it.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0">
          {isAutoPrompt ? (
            <Button variant="outline" onClick={handleDisableAutoSave} disabled={isSubmitting}>
              Stop auto-save for this agent
            </Button>
          ) : (
            <Button variant="outline" onClick={handleClose} disabled={isSubmitting}>
              Cancel
            </Button>
          )}
          <Button onClick={handleCreateVersion} disabled={isSubmitting}>
            Create {nextVersionLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default VersionSavePrompt;
