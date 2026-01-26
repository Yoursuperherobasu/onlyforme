import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/pages/ApprovalPage/components/Avatar";
import {
  User,
  FolderOpen,
  Calendar,
  GitBranch,
  MoreVertical,
} from "lucide-react";

interface AgentCardProps {
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
  return (
    <div className="rounded-lg border bg-card p-6 transition-all hover:shadow-md">
      {/* Header */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-medium">{title}</h3>
          {status === "pending" && (
            <Badge variant="secondary">
              Pending Review
            </Badge>
          )}
        </div>
        <button className="text-muted-foreground hover:text-foreground">
          <MoreVertical className="h-5 w-5" />
        </button>
      </div>

      {/* Description */}
      <p className="mb-6 text-sm text-muted-foreground">
        {description}
      </p>

      {/* Meta */}
      <div className="mb-6 grid grid-cols-4 gap-6 text-sm">
        <MetaItem icon={<User />} label="Submitted By">
          <div className="flex items-center gap-2">
            <Avatar className="h-5 w-5">
              <AvatarImage src={submittedBy.avatar} />
              <AvatarFallback>
                {submittedBy.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")}
              </AvatarFallback>
            </Avatar>
            {submittedBy.name}
          </div>
        </MetaItem>

        <MetaItem icon={<FolderOpen />} label="Project">
          {project}
        </MetaItem>

        <MetaItem icon={<Calendar />} label="Submitted">
          {submitted}
        </MetaItem>

        <MetaItem icon={<GitBranch />} label="Version">
          {version}
        </MetaItem>
      </div>

      {/* Recent Changes */}
      <div className="mb-6 rounded-md bg-accent p-4">
        <div className="text-xs text-muted-foreground">
          Recent Changes
        </div>
        <div className="text-sm">{recentChanges}</div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <div className="flex gap-4">
          <button
            onClick={onReviewDetails}
            className="text-sm hover:underline"
          >
            Review Details
          </button>
          <button
            onClick={onRunTest}
            className="text-sm hover:underline"
          >
            Run Test
          </button>
        </div>

        <div className="flex gap-3">
          <Button
            variant="outline"
            className="text-destructive"
            onClick={onReject}
          >
            Reject
          </Button>
          <Button onClick={onApprove}>
            Approve
          </Button>
        </div>
      </div>
    </div>
  );
}

function MetaItem({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-2">
      <div className="mt-0.5 text-muted-foreground">
        {icon}
      </div>
      <div>
        <div className="text-xs text-muted-foreground">
          {label}
        </div>
        <div>{children}</div>
      </div>
    </div>
  );
}