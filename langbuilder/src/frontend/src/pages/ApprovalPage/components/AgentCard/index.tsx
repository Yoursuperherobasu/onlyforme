import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, Play, FileText } from "lucide-react";

interface AgentCardProps {
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
  onReject: () => void;
  onApprove: () => void;
  onReviewDetails: () => void;
  onRunTest: () => void;
}

export function AgentCard({
  title,
  status,
  description,
  submittedBy,
  project,
  submitted,
  version,
  recentChanges,
  onReject,
  onApprove,
  onReviewDetails,
  onRunTest,
}: AgentCardProps) {
  const statusColors = {
    pending: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    approved: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    rejected: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };

  return (
    <div className="rounded-lg border border-border bg-card p-6 transition-shadow hover:shadow-md">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div className="flex-1">
          <div className="mb-2 flex items-center gap-3">
            <h3 className="text-lg font-semibold">{title}</h3>
            <span
              className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColors[status]}`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>

      {/* Metadata */}
      <div className="mb-4 grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
        <div>
          <div className="text-xs text-muted-foreground">Submitted By</div>
          <div className="font-medium">{submittedBy.name}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Project</div>
          <div className="font-medium">{project}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Version</div>
          <div className="font-medium">{version}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Submitted</div>
          <div className="font-medium">{submitted}</div>
        </div>
      </div>

      {/* Recent Changes */}
      <div className="mb-4 rounded-md bg-muted/50 p-3">
        <div className="mb-1 text-xs font-medium text-muted-foreground">
          Recent Changes
        </div>
        <div className="text-sm">{recentChanges}</div>
      </div>

      {/* Actions */}
      {/* Actions */}
<div className="flex w-full items-center gap-2">
  {/* LEFT actions */}
  <div className="flex flex-wrap items-center gap-2">
    <Button variant="outline" onClick={onReviewDetails} className="gap-2">
      <FileText className="h-4 w-4" />
      Review Details
    </Button>
    <Button variant="outline" onClick={onRunTest} className="gap-2">
      <Play className="h-4 w-4" />
      Run Test
    </Button>
  </div>

  {/* RIGHT actions */}
  {status === "pending" && (
    <div className="ml-auto flex items-center gap-2">
      

     <Button
  variant="outline"
  onClick={onReject}
  className="
    gap-2
    border-red-500 text-red-600
    hover:!bg-red-50 hover:!text-red-600
    dark:border-red-700 dark:text-red-400
    dark:hover:!bg-red-950/30 dark:hover:!text-red-400
  "
>
  <XCircle className="h-4 w-4" />
  Reject
</Button>


      <Button
  variant="outline"
  onClick={onApprove}
  className="
    gap-2
    border-green-500 text-green-600
    hover:!bg-green-50 hover:!text-green-600
    dark:border-green-700 dark:text-green-400
    dark:hover:!bg-green-950/30 dark:hover:!text-green-400
  "
>
  <CheckCircle2 className="h-4 w-4" />
  Approve
</Button>

    </div>
  )}
</div>

    </div>
  );
}