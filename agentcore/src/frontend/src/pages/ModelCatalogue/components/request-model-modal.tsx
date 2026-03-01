import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import useAlertStore from "@/stores/alertStore";

interface RequestModelModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "azure", label: "Azure OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google" },
  { value: "groq", label: "Groq" },
  { value: "openai_compatible", label: "Custom Model" },
];

export default function RequestModelModal({
  open,
  onOpenChange,
}: RequestModelModalProps) {
  const [displayName, setDisplayName] = useState("");
  const [provider, setProvider] = useState("openai");
  const [modelName, setModelName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [chargeCode, setChargeCode] = useState("");
  const [projectName, setProjectName] = useState("");
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const resetForm = () => {
    setDisplayName("");
    setProvider("openai");
    setModelName("");
    setBaseUrl("");
    setChargeCode("");
    setProjectName("");
    setReason("");
  };

  const handleClose = () => {
    onOpenChange(false);
    resetForm();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chargeCode.trim() || !projectName.trim() || !reason.trim()) {
      return;
    }
    setIsSubmitting(true);
    await new Promise((resolve) => setTimeout(resolve, 500));
    setSuccessData({
      title: "Model request submitted (dummy)",
    });
    setIsSubmitting(false);
    handleClose();
  };

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] w-full max-w-2xl flex-col gap-0 overflow-hidden p-0">
        <div className="flex-shrink-0 border-b p-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-semibold">Request New Model</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Share model details for admin review and onboarding
              </p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Basic Information
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Display Name *</Label>
                <Input
                  required
                  placeholder="e.g., GPT-4.1 for Analytics"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>
              <div>
                <Label>Provider *</Label>
                <select
                  required
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Model Name / ID *</Label>
                <Input
                  required
                  placeholder="e.g., gpt-4.1-mini"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                />
              </div>
              <div>
                <Label>Base URL</Label>
                <Input
                  placeholder="https://api.example.com/v1"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                />
              </div>
            </div>
          </fieldset>

          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Request Details
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Charge Code *</Label>
                <Input
                  required
                  placeholder="e.g., CC-1042"
                  value={chargeCode}
                  onChange={(e) => setChargeCode(e.target.value)}
                />
              </div>
              <div>
                <Label>Project Name *</Label>
                <Input
                  required
                  placeholder="e.g., Customer Support Revamp"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                />
              </div>
            </div>

            <div>
              <Label>Reason *</Label>
              <Textarea
                required
                rows={4}
                placeholder="Tell admins why this model is needed and expected use-case."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
          </fieldset>
        </form>

        <div className="flex-shrink-0 border-t p-6">
          <div className="flex items-center gap-3">
            <div className="flex-1" />
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Submit Request
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
