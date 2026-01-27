import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

interface ActionModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  action: "approve" | "reject";
  agentTitle: string;
  onSubmit: (comments: string) => void;
}

export default function ActionModal({
  open,
  setOpen,
  action,
  agentTitle,
  onSubmit,
}: ActionModalProps) {
  const [comments, setComments] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(comments);
    setComments("");
    setOpen(false);
  };

  const handleClose = () => {
    setComments("");
    setOpen(false);
  };

  if (!open) return null;

  const isApprove = action === "approve";

  return (
    <>
      {/* Backdrop with blur */}
      <div
        className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="fixed left-[50%] top-[50%] z-50 w-full max-w-lg translate-x-[-50%] translate-y-[-50%] rounded-lg border border-border bg-card p-6 shadow-lg">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-card-foreground">
              {isApprove ? "Approve Agent" : "Reject Agent"}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">{agentTitle}</p>
          </div>
          <button
            onClick={handleClose}
            className="rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100"
          >
            <X className="h-5 w-5" />
            <span className="sr-only">Close</span>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Comments */}
          <div className="space-y-2">
            <Label htmlFor="comments" className="text-sm font-medium">
              Comments {!isApprove && <span className="text-destructive">*</span>}
            </Label>
            <Textarea
              id="comments"
              required={!isApprove}
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder={
                isApprove
                  ? "Add optional feedback or notes..."
                  : "Please provide a reason for rejection..."
              }
              rows={5}
              className="resize-none bg-background"
            />
            {!isApprove && (
              <p className="text-xs text-muted-foreground">
                Rejection reason is required
              </p>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant={isApprove ? "default" : "destructive"}
              className="flex-1"
            >
              {isApprove ? "Approve" : "Reject"}
            </Button>
          </div>
        </form>
      </div>
    </>
  );
}