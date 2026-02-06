import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ModelType } from "@/types/models/models";

interface EditModelModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model?: ModelType;
  onSave: (data: Partial<ModelType>) => void;
}

export default function EditModelModal({
  open,
  onOpenChange,
  model,
  onSave,
}: EditModelModalProps) {
  const [formData, setFormData] = useState({
    name: "",
    provider: "",
    apiEndpoint: "",
    apiKey: "",
    contextWindow: "",
    description: "",
  });

  useEffect(() => {
    if (open) {
      setFormData({
        name: model?.name ?? "",
        provider: model?.provider ?? "",
        apiEndpoint: model?.apiEndpoint ?? "",
        apiKey: model?.apiKey ?? "",
        contextWindow: model?.contextWindow ?? "",
        description: model?.description ?? "",
      });
    }
  }, [model, open]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData);
    onOpenChange(false);
  };

  const handleClose = () => onOpenChange(false);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold">
              {model ? "Configure Model" : "Add Custom Model"}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {model
                ? "Update model configuration and settings"
                : "Connect your own AI model"}
            </p>
          </div>

          <button
            onClick={handleClose}
            className="rounded-sm opacity-70 transition-opacity hover:opacity-100"
          >
            <X className="h-5 w-5" />
            <span className="sr-only">Close</span>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Model Name */}
          <div>
            <Label>Model Name *</Label>
            <Input
              required
              placeholder="e.g., GPT-4, Claude 3, Custom LLM"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
            />
          </div>

          {/* Provider */}
          <div>
            <Label>Provider *</Label>
            <Input
              required
              placeholder="e.g., OpenAI, Custom, Self-hosted"
              value={formData.provider}
              onChange={(e) =>
                setFormData({ ...formData, provider: e.target.value })
              }
            />
          </div>

          {/* API Endpoint */}
          <div>
            <Label>API Endpoint *</Label>
            <Input
              type="url"
              required
              placeholder="https://api.example.com/v1/completions"
              value={formData.apiEndpoint}
              onChange={(e) =>
                setFormData({ ...formData, apiEndpoint: e.target.value })
              }
            />
          </div>

          {/* API Key */}
          <div>
            <Label>API Key *</Label>
            <Input
              type="password"
              required
              placeholder="sk-..."
              value={formData.apiKey}
              onChange={(e) =>
                setFormData({ ...formData, apiKey: e.target.value })
              }
            />
            <p className="text-xs text-muted-foreground">
              Your API key is stored securely and never shared
            </p>
          </div>

          {/* Context Window */}
          <div>
            <Label>Context Window</Label>
            <Input
              placeholder="e.g., 8K tokens, 128K tokens"
              value={formData.contextWindow}
              onChange={(e) =>
                setFormData({ ...formData, contextWindow: e.target.value })
              }
            />
          </div>

          {/* Description */}
          <div>
            <Label>Description</Label>
            <Textarea
              rows={3}
              placeholder="Brief description of the model and its capabilities"
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button type="submit" className="flex-1">
              {model ? "Save Changes" : "+ Add Model"}
            </Button>
          </div>
        </form>
      </div>
    </>
  );
}
