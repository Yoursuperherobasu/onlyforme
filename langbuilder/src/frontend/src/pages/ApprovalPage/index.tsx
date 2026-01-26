import { useState } from "react";
import { AgentCard } from "./components/AgentCard";
import { Button } from "@/components/ui/button";

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

  const filteredAgents = agents.filter((agent) =>
    filter === "all" ? true : agent.status === filter,
  );

  const counts = {
    all: agents.length,
    pending: agents.filter((a) => a.status === "pending").length,
    approved: agents.filter((a) => a.status === "approved").length,
    rejected: agents.filter((a) => a.status === "rejected").length,
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-6xl px-8 py-8">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold">
              Human in the Loop
            </h1>
            <p className="text-sm text-muted-foreground">
              Review and approve AI agents before deployment
            </p>
          </div>

          <div className="rounded-md border bg-card px-4 py-2">
            <span className="font-medium">
              {counts.pending} Pending
            </span>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="mb-8 flex gap-3">
          {(["all", "pending", "approved", "rejected"] as FilterType[]).map(
            (type) => (
              <Button
                key={type}
                variant={filter === type ? "default" : "outline"}
                onClick={() => setFilter(type)}
              >
                {type.charAt(0).toUpperCase() + type.slice(1)}
                <span className="ml-2 text-muted-foreground">
                  {counts[type]}
                </span>
              </Button>
            ),
          )}
        </div>

        {/* Agent Cards */}
        <div className="space-y-6">
          {filteredAgents.map((agent) => (
            <AgentCard
              key={agent.id}
              {...agent}
              onReject={() => console.log("Reject", agent.id)}
              onApprove={() => console.log("Approve", agent.id)}
              onReviewDetails={() =>
                console.log("Review Details", agent.id)
              }
              onRunTest={() => console.log("Run Test", agent.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}