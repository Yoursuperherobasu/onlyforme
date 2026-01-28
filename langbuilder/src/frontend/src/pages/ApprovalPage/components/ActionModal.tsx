import { useState } from "react";
import { X, Upload, File, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

interface ActionModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  action: "approve" | "reject";
  agentTitle: string;
  onSubmit: (data: { comments: string; attachments: File[] }) => void;
}

export default function ActionModal({
  open,
  setOpen,
  action,
  agentTitle,
  onSubmit,
}: ActionModalProps) {
  const [comments, setComments] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validation: Either comments or attachments must be provided
    if (!comments.trim() && attachments.length === 0) {
      setError("Please provide either comments or attachments");
      return;
    }

    onSubmit({ comments, attachments });
    handleClose();
  };

  const handleClose = () => {
    setComments("");
    setAttachments([]);
    setError("");
    setOpen(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setAttachments([...attachments, ...files]);
    setError(""); // Clear error when files are added
  };

  const handleRemoveFile = (index: number) => {
    setAttachments(attachments.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
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
          {/* Error Message */}
          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {/* Comments */}
          <div className="space-y-2">
            <Label htmlFor="comments" className="text-sm font-medium">
              Comments
            </Label>
            <Textarea
              id="comments"
              value={comments}
              onChange={(e) => {
                setComments(e.target.value);
                setError(""); // Clear error when typing
              }}
              placeholder={
                isApprove
                  ? "Add optional feedback or notes..."
                  : "Please provide a reason for rejection..."
              }
              rows={5}
              className="resize-none bg-background"
            />
          </div>

          {/* File Attachments */}
          <div className="space-y-2">
            <Label htmlFor="attachments" className="text-sm font-medium">
              Attachments
            </Label>
            
            {/* Upload Button */}
            <div className="flex items-center gap-2">
              <input
                id="attachments"
                type="file"
                multiple
                onChange={handleFileChange}
                className="hidden"
                accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.xlsx,.csv"
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => document.getElementById("attachments")?.click()}
                className="w-full gap-2"
              >
                <Upload className="h-4 w-4" />
                Upload Files
              </Button>
            </div>

            {/* File List */}
            {attachments.length > 0 && (
              <div className="mt-3 space-y-2">
                {attachments.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between rounded-md border border-border bg-muted/50 p-3"
                  >
                    <div className="flex items-center gap-3">
                      <File className="h-4 w-4 text-muted-foreground" />
                      <div className="flex flex-col">
                        <span className="text-sm font-medium">
                          {file.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatFileSize(file.size)}
                        </span>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveFile(index)}
                      className="h-8 w-8 p-0 hover:bg-destructive/10 hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              {isApprove
                ? "Either comments or attachments are required"
                : "Either comments or attachments are required for rejection"}
            </p>
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