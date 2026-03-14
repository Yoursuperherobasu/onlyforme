import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AgentCard } from "./components/AgentCard";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";
import ActionModal from "./components/ActionModal";
import McpConfigModal from "./components/McpConfigModal";
import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext";
import useAlertStore from "@/stores/alertStore";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useDeployPackageRequest, useGetPackageRequestsForApproval } from "@/controllers/API/queries/packages";

import { useGetApprovals, type ApprovalAgent } from "@/controllers/API/queries/approvals";
import { useApprovalActionModal, useApprovalActions } from "./hooks";
import CustomLoader from "@/customization/components/custom-loader";

type FilterType = "all" | "pending" | "approved" | "rejected" | "deployed" | "cancelled";
type ApprovalTabType = "agent" | "model" | "mcp" | "package";

const APPROVAL_TABS: Array<{ id: ApprovalTabType; label: string; permission: string }> = [
  { id: "agent", label: "AI Agent", permission: "view_agent" },
  { id: "model", label: "Model", permission: "view_model" },
  { id: "mcp", label: "MCP", permission: "view_mcp" },
  { id: "package", label: "Package", permission: "view_packages_page" },
];

export default function ApprovalPage() {
  const { t } = useTranslation();
  /* ================= STATE ================= */
  const [filter, setFilter] = useState<FilterType>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<ApprovalTabType>("agent");
  const navigate = useCustomNavigate();
  const { permissions, role } = useContext(AuthContext);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const can = (permissionKey: string) => permissions?.includes(permissionKey);
  const isRoot = String(role ?? "").toLowerCase() === "root";
  const [isMcpConfigOpen, setIsMcpConfigOpen] = useState(false);
  const [selectedMcpApprovalId, setSelectedMcpApprovalId] = useState<string | null>(null);

  /* ================= MODAL & ACTIONS MANAGEMENT ================= */
  const { isOpen, selectedAgent, action, openModal, closeModal } =
    useApprovalActionModal();
  const { handleApprove, handleReject } = useApprovalActions();

  /* ================= API QUERIES ================= */
  // Fetch all approvals from backend
  const { data: agents = [], isLoading: isLoadingAgents } = useGetApprovals();
  const { data: packageRequests = [], isLoading: isLoadingPackageRequests } =
    useGetPackageRequestsForApproval(
      {},
      {
        enabled: isRoot,
      },
    );
  const deployPackageRequestMutation = useDeployPackageRequest();

  const visibleTabs = isRoot
    ? APPROVAL_TABS.filter((tab) => tab.id === "package")
    : APPROVAL_TABS.filter((tab) => tab.id !== "package" && can(tab.permission));

  useEffect(() => {
    if (visibleTabs.length === 0) return;
    if (!visibleTabs.some((tab) => tab.id === activeTab)) {
      setActiveTab(visibleTabs[0].id);
    }
  }, [activeTab, visibleTabs]);

  useEffect(() => {
    if (activeTab !== "package" && (filter === "deployed" || filter === "cancelled")) {
      setFilter("all");
    }
  }, [activeTab, filter]);

  /* ================= FILTERING & CALCULATIONS ================= */
  const packageApprovalCards: ApprovalAgent[] = packageRequests.map((request) => ({
    id: request.id,
    entityType: "package",
    title: `${request.package_name}`,
    status: request.status,
    description: request.justification,
    submittedBy: {
      name:
        request.requested_by_name ||
        request.requested_by_email ||
        request.requested_by,
      email: request.requested_by_email ?? null,
    },
    project: request.service_name,
    submitted: request.requested_at,
    version: request.requested_version,
    recentChanges: request.review_comments || request.deployment_notes || "-",
  }));

  const sourceApprovals = activeTab === "package" ? packageApprovalCards : agents;

  const filteredAgents = sourceApprovals.filter((agent) => {
    const entityType = (agent.entityType || "agent") as ApprovalTabType;
    const matchesTab = entityType === activeTab;
    const matchesFilter = filter === "all" ? true : agent.status === filter;
    const matchesSearch =
      searchQuery === "" ||
      agent.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.project.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesFilter && matchesSearch;
  });

  const pendingCount = sourceApprovals.filter((a) => a.status === "pending").length;
  const noAgentsMessage =
    filter === "pending"
      ? t("No pending agents found")
      : filter === "approved"
        ? t("No approved agents found")
        : filter === "rejected"
          ? t("No rejected agents found")
          : filter === "deployed"
            ? t("No deployed requests found")
            : filter === "cancelled"
              ? t("No cancelled requests found")
              : t("No agents found");

  useEffect(() => {
    if (pendingCount > 0) {
      setNoticeData({
        title: t("{{count}} publish request(s) awaiting your approval.", {
          count: pendingCount,
        }),
      });
    }
  }, [pendingCount, setNoticeData, t]);

  /* ================= EVENT HANDLERS ================= */
  const handleApproveClick = (agent: ApprovalAgent) => {
    openModal(agent, "approve");
  };

  const handleRejectClick = (agent: ApprovalAgent) => {
    openModal(agent, "reject");
  };

  const handleMcpConfigClick = (agent: ApprovalAgent) => {
    if ((agent.entityType || "agent") !== "mcp") return;
    setSelectedMcpApprovalId(agent.id);
    setIsMcpConfigOpen(true);
  };

  const handlePackageDeploy = async (agent: ApprovalAgent) => {
    await new Promise((resolve, reject) => {
      deployPackageRequestMutation.mutate(
        {
          requestId: agent.id,
          deployment_notes: "Marked as deployed by root admin",
        },
        {
          onSuccess: () => {
            setSuccessData({ title: `Package "${agent.title}" marked as deployed.` });
            resolve(null);
          },
          onError: () => {
            setErrorData({ title: `Failed to mark package "${agent.title}" as deployed.` });
            reject(new Error("Package deploy action failed"));
          },
        },
      );
    });
  };

  /**
   * Handle the final action submission from the modal
   * Calls either handleApprove or handleReject based on the action type
   */
  const handleSubmitAction = async (data: {
    comments: string;
    attachments: File[];
  }) => {
    if (!selectedAgent) return;

    if (action === "approve") {
      await handleApprove(selectedAgent, data.comments, data.attachments);
    } else {
      await handleReject(selectedAgent, data.comments, data.attachments);
    }

  };

  return (
    <div className="flex h-full w-full flex-col overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="text-2xl font-semibold">{t("Review & Approval")}</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("Review and approve model, MCP, AI agent, and package requests")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder={t("Search agents...")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 rounded-lg border border-border bg-card py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-3 border-b border-border px-8 py-4">
        {visibleTabs.map((tab) => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? "default" : "outline"}
            onClick={() => setActiveTab(tab.id)}
          >
            {t(tab.label)}
          </Button>
        ))}
      </div>

      {/* Status Tabs */}
      <div className="flex items-center gap-3 border-b border-border px-8 py-4">
        {(activeTab === "package"
          ? (["all", "pending", "approved", "rejected", "deployed", "cancelled"] as FilterType[])
          : (["all", "pending", "approved", "rejected"] as FilterType[])
        ).map((type) => (
          <Button
            key={type}
            variant={filter === type ? "default" : "outline"}
            onClick={() => setFilter(type)}
          >
            {t(type.charAt(0).toUpperCase() + type.slice(1))}
          </Button>
        ))}
      </div>

      {/* Agent Cards */}
      <div className="flex-1 overflow-auto p-8">
        {isLoadingAgents || (activeTab === "package" && isLoadingPackageRequests) ? (
          <div className="flex h-full items-center justify-center">
            <CustomLoader />
          </div>
        ) : (
          <div className="space-y-6">
            {filteredAgents.length === 0 ? (
              <div className="rounded-lg border border-border bg-card p-12 text-center">
                <p className="text-muted-foreground">
                  {searchQuery
                    ? t("No agents found matching your search")
                    : noAgentsMessage}
                </p>
              </div>
            ) : (
              filteredAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  {...agent}
                  entityType={agent.entityType}
                  onReject={() => handleRejectClick(agent)}
                  onApprove={() => handleApproveClick(agent)}
                  onReviewDetails={() =>
                    agent.entityType === "mcp"
                      ? setErrorData({ title: t("Use MCP Config for MCP approvals") })
                      : agent.entityType === "package"
                        ? undefined
                      : navigate(`/approval/${agent.id}/review`)
                  }
                  onViewMcpConfig={() => handleMcpConfigClick(agent)}
                  onDeploy={() => handlePackageDeploy(agent)}
                />
              ))
            )}
          </div>
        )}

      </div>

      {/* Action Modal */}
      <ActionModal
        open={isOpen}
        setOpen={closeModal}
        action={action}
        entityType={selectedAgent?.entityType}
        agentTitle={selectedAgent?.title || ""}
        onSubmit={handleSubmitAction}
      />
      <McpConfigModal
        open={isMcpConfigOpen}
        setOpen={setIsMcpConfigOpen}
        approvalId={selectedMcpApprovalId}
      />
    </div>
  );
}
