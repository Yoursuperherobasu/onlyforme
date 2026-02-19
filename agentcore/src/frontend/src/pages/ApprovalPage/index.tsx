import { useEffect, useState } from "react";
import { AgentCard } from "./components/AgentCard";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";
import ActionModal from "./components/ActionModal";
import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext";
import useAlertStore from "@/stores/alertStore";

import { useGetApprovals, type ApprovalAgent } from "@/controllers/API/queries/approvals";
import { useApprovalActionModal, useApprovalActions } from "./hooks";
import CustomLoader from "@/customization/components/custom-loader";

type FilterType = "all" | "pending" | "approved" | "rejected";
type ApprovalTabType = "agent" | "model" | "mcp";

const APPROVAL_TABS: Array<{ id: ApprovalTabType; label: string; permission: string }> = [
  { id: "agent", label: "Agent", permission: "view_agent" },
  { id: "model", label: "Model", permission: "view_model" },
  { id: "mcp", label: "MCP", permission: "view_mcp" },
];

// Hardcoded mapping for now; API/DB-backed mapping can replace this later.
const APPROVAL_ENTITY_TYPE_BY_ID: Record<string, ApprovalTabType> = {};

export default function ApprovalPage() {
  /* ================= STATE ================= */
  const [filter, setFilter] = useState<FilterType>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<ApprovalTabType>("agent");
  const { permissions } = useContext(AuthContext);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const can = (permissionKey: string) => permissions?.includes(permissionKey);

  /* ================= MODAL & ACTIONS MANAGEMENT ================= */
  const { isOpen, selectedAgent, action, openModal, closeModal } =
    useApprovalActionModal();
  const { handleApprove, handleReject, isLoading } = useApprovalActions();

  /* ================= API QUERIES ================= */
  // Fetch all approvals from backend
  const { data: agents = [], isLoading: isLoadingAgents } = useGetApprovals();
  const visibleTabs = APPROVAL_TABS.filter((tab) => can(tab.permission));

  useEffect(() => {
    if (visibleTabs.length === 0) return;
    if (!visibleTabs.some((tab) => tab.id === activeTab)) {
      setActiveTab(visibleTabs[0].id);
    }
  }, [activeTab, visibleTabs]);

  /* ================= FILTERING & CALCULATIONS ================= */
  const filteredAgents = agents.filter((agent) => {
    const entityType = APPROVAL_ENTITY_TYPE_BY_ID[agent.id] || "agent";
    const matchesTab = entityType === activeTab;
    const matchesFilter = filter === "all" ? true : agent.status === filter;
    const matchesSearch =
      searchQuery === "" ||
      agent.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.project.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesFilter && matchesSearch;
  });

  const counts = {
    all: agents.length,
    pending: agents.filter((a) => a.status === "pending").length,
    approved: agents.filter((a) => a.status === "approved").length,
    rejected: agents.filter((a) => a.status === "rejected").length,
  };

  useEffect(() => {
    if (counts.pending > 0) {
      setNoticeData({
        title: `${counts.pending} publish request(s) awaiting your approval.`,
      });
    }
  }, [counts.pending, setNoticeData]);

  /* ================= EVENT HANDLERS ================= */
  const handleApproveClick = (agent: ApprovalAgent) => {
    openModal(agent, "approve");
  };

  const handleRejectClick = (agent: ApprovalAgent) => {
    openModal(agent, "reject");
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

    // Close modal after action completes
    closeModal();
  };

  return (
    <div className="flex h-full w-full flex-col overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="text-2xl font-semibold">Review & Approval</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Review and approve AI agents before deployment
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search agents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 rounded-lg border border-border bg-card py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          {/* Pending Count Badge */}
          <div className="rounded-md border border-border bg-card px-4 py-2.5">
            <span className="text-sm font-medium">{counts.pending} Pending</span>
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
            {tab.label}
          </Button>
        ))}
      </div>

      {/* Status Tabs */}
      <div className="flex items-center gap-3 border-b border-border px-8 py-4">
        {(["all", "pending", "approved", "rejected"] as FilterType[]).map(
          (type) => (
            <Button
              key={type}
              variant={filter === type ? "default" : "outline"}
              onClick={() => setFilter(type)}
              className="gap-2"
            >
              <span>{type.charAt(0).toUpperCase() + type.slice(1)}</span>
              <span
                className={
                  filter === type ? "opacity-80" : "text-muted-foreground"
                }
              >
                {counts[type]}
              </span>
            </Button>
          ),
        )}
      </div>

      {/* Agent Cards */}
      <div className="flex-1 overflow-auto p-8">
        {isLoadingAgents ? (
          <div className="flex h-full items-center justify-center">
            <CustomLoader />
          </div>
        ) : (
          <div className="space-y-6">
            {filteredAgents.length === 0 ? (
              <div className="rounded-lg border border-border bg-card p-12 text-center">
                <p className="text-muted-foreground">
                  {searchQuery
                    ? "No agents found matching your search"
                    : `No ${filter !== "all" ? filter : ""} agents found`}
                </p>
              </div>
            ) : (
              filteredAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  {...agent}
                  onReject={() => handleRejectClick(agent)}
                  onApprove={() => handleApproveClick(agent)}
                  onReviewDetails={() => console.log("Review Details", agent.id)}
                  onRunTest={() => console.log("Run Test", agent.id)}
                />
              ))
            )}
          </div>
        )}

        {/* Footer Stats */}
        {filteredAgents.length > 0 && (
          <div className="mt-6 text-center text-sm text-muted-foreground">
            Showing {filteredAgents.length} of {agents.length} Agents
          </div>
        )}
      </div>

      {/* Action Modal */}
      <ActionModal
        open={isOpen}
        setOpen={closeModal}
        action={action}
        agentTitle={selectedAgent?.title || ""}
        onSubmit={handleSubmitAction}
        isLoading={isLoading}
      />
    </div>
  );
}
