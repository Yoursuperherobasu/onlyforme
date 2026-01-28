import { useState } from "react";
import { AgentCard } from "./components/AgentCard";
import { Button } from "@/components/ui/button";
import { Search, Users } from "lucide-react";
import ActionModal from "./components/ActionModal";

type FilterType = "all" | "pending" | "approved" | "rejected";

interface Agent {
  id: string;
  title: string;
  status: "pending" | "approved" | "rejected";
  description: string;
  submittedBy: {
    name: string;
    avatar?: string;
  };
  project: string;
  submitted: string;
  version: string;
  recentChanges: string;
}

const agents: Agent[] = [
  {
    id: "1",
    title: "Customer Support Agent",
    status: "pending",
    description:
      "Handles customer inquiries with context-aware responses and sentiment analysis.",
    submittedBy: { name: "Max Leiter" },
    project: "E-Commerce Platform",
    submitted: "2h ago",
    version: "v2.1.0",
    recentChanges: "Updated NLP model, improved response accuracy",
  },
  {
    id: "2",
    title: "Data Analysis Pipeline",
    status: "pending",
    description:
      "Processes large datasets with anomaly detection and insight generation.",
    submittedBy: { name: "Arya Manisha" },
    project: "Analytics Dashboard",
    submitted: "5h ago",
    version: "v1.8.2",
    recentChanges: "Added real-time processing",
  },
];

export default function ApprovalPage() {
  const [filter, setFilter] = useState<FilterType>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [modalAction, setModalAction] = useState<"approve" | "reject">("approve");
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  const filteredAgents = agents.filter((agent) => {
    const matchesFilter = filter === "all" ? true : agent.status === filter;
    const matchesSearch =
      searchQuery === "" ||
      agent.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.project.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const counts = {
    all: agents.length,
    pending: agents.filter((a) => a.status === "pending").length,
    approved: agents.filter((a) => a.status === "approved").length,
    rejected: agents.filter((a) => a.status === "rejected").length,
  };

  const handleApprove = (agent: Agent) => {
    setSelectedAgent(agent);
    setModalAction("approve");
    setModalOpen(true);
  };

  const handleReject = (agent: Agent) => {
    setSelectedAgent(agent);
    setModalAction("reject");
    setModalOpen(true);
  };

  const handleSubmitAction = (comments: string) => {
    console.log(`${modalAction} agent:`, selectedAgent?.id);
    console.log("Comments:", comments);
    // TODO: Add API call here
  };

  return (
    <div className="flex h-full w-full flex-col overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <Users className="h-7 w-7 text-blue-500" />
            <h1 className="text-2xl font-semibold">Approvals</h1>
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
                    filter === type
                      ? "opacity-80"
                      : "text-muted-foreground"
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
                onReject={() => handleReject(agent)}
                onApprove={() => handleApprove(agent)}
                onReviewDetails={() =>
                  console.log("Review Details", agent.id)
                }
                onRunTest={() => console.log("Run Test", agent.id)}
              />
            ))
          )}
        </div>

        {/* Footer Stats */}
        {filteredAgents.length > 0 && (
          <div className="mt-6 text-center text-sm text-muted-foreground">
            Showing {filteredAgents.length} of {agents.length} Agents
          </div>
        )}
      </div>

      {/* Action Modal */}
      <ActionModal
        open={modalOpen}
        setOpen={setModalOpen}
        action={modalAction}
        agentTitle={selectedAgent?.title || ""}
        onSubmit={handleSubmitAction}
      />
    </div>
  );
}