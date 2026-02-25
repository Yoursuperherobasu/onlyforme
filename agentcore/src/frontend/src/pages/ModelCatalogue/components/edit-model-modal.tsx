import { useState, useEffect } from "react";
import { X, Loader2, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  ModelType,
  ModelCreateRequest,
  ModelUpdateRequest,
  ModelEnvironment,
} from "@/types/models/models";
import useAlertStore from "@/stores/alertStore";
import {
  usePostRegistryModel,
  usePutRegistryModel,
  useTestModelConnection,
} from "@/controllers/API/queries/models";

const PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "azure", label: "Azure OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google" },
  { value: "groq", label: "Groq" },
  { value: "openai_compatible", label: "Custom Model" },
];

const DEFAULT_AZURE_API_VERSION = "2025-10-01-preview";

const ENVIRONMENTS: { value: ModelEnvironment; label: string }[] = [
  { value: "test", label: "Test" },
  { value: "uat", label: "UAT" },
  { value: "prod", label: "Production" },
];

interface EditModelModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model?: ModelType | null;
}

export default function EditModelModal({
  open,
  onOpenChange,
  model,
}: EditModelModalProps) {
  const isEditMode = !!model;

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const createMutation = usePostRegistryModel();
  const updateMutation = usePutRegistryModel();
  const testMutation = useTestModelConnection();

  /* ---------------------------------- Form State ---------------------------------- */

  const [displayName, setDisplayName] = useState("");
  const [provider, setProvider] = useState("openai");
  const [modelName, setModelName] = useState("");
  const [description, setDescription] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [environment, setEnvironment] = useState<ModelEnvironment>("test");
  const [isActive, setIsActive] = useState(true);

  // Provider-specific
  const [azureDeployment, setAzureDeployment] = useState("");
  const [azureApiVersion, setAzureApiVersion] = useState(DEFAULT_AZURE_API_VERSION);
  const [organization, setOrganization] = useState("");
  const [customHeaders, setCustomHeaders] = useState("");

  // Capabilities
  const [supportsStreaming, setSupportsStreaming] = useState(true);
  const [supportsToolCalling, setSupportsToolCalling] = useState(false);
  const [supportsVision, setSupportsVision] = useState(false);
  const [supportsThinking, setSupportsThinking] = useState(false);
  const [contextWindow, setContextWindow] = useState<number | "">("");

  // Default params
  const [temperature, setTemperature] = useState<number | "">(0.7);
  const [maxTokens, setMaxTokens] = useState<number | "">("");
  const [topP, setTopP] = useState<number | "">("");
  const [thinkingBudget, setThinkingBudget] = useState<number | "">("");

  /* ---------------------------------- Populate form on edit ---------------------------------- */

  useEffect(() => {
    if (!open) return;

    if (model) {
      setDisplayName(model.display_name);
      setProvider(model.provider);
      setModelName(model.model_name);
      setDescription(model.description ?? "");
      setApiKey(""); // never pre-fill
      setBaseUrl(model.base_url ?? "");
      setEnvironment(model.environment ?? "test");
      setIsActive(model.is_active);

      const pc = model.provider_config ?? {};
      setAzureDeployment(pc.azure_deployment ?? "");
      setAzureApiVersion(pc.api_version ?? DEFAULT_AZURE_API_VERSION);
      setOrganization(pc.organization ?? "");
      setCustomHeaders(pc.custom_headers ? JSON.stringify(pc.custom_headers, null, 2) : "");

      const caps = model.capabilities ?? {};
      setSupportsStreaming(caps.supports_streaming ?? true);
      setSupportsToolCalling(caps.supports_tool_calling ?? false);
      setSupportsVision(caps.supports_vision ?? false);
      setSupportsThinking(caps.supports_thinking ?? false);
      setContextWindow(caps.context_window ?? "");

      const dp = model.default_params ?? {};
      setTemperature(dp.temperature ?? 0.7);
      setMaxTokens(dp.max_tokens ?? "");
      setTopP(dp.top_p ?? "");
      setThinkingBudget(dp.thinking_budget ?? "");
    } else {
      // Reset for create
      setDisplayName("");
      setProvider("openai");
      setModelName("");
      setDescription("");
      setApiKey("");
      setBaseUrl("");
      setEnvironment("test");
      setIsActive(true);
      setAzureDeployment("");
      setAzureApiVersion(DEFAULT_AZURE_API_VERSION);
      setOrganization("");
      setCustomHeaders("");
      setSupportsStreaming(true);
      setSupportsToolCalling(false);
      setSupportsVision(false);
      setSupportsThinking(false);
      setContextWindow("");
      setTemperature(0.7);
      setMaxTokens("");
      setTopP("");
      setThinkingBudget("");
    }
  }, [model, open]);

  /* ---------------------------------- Build payload ---------------------------------- */

  const buildProviderConfig = (): Record<string, any> | undefined => {
    const config: Record<string, any> = {};
    if (provider === "azure") {
      if (azureDeployment) config.azure_deployment = azureDeployment;
      if (azureApiVersion) config.api_version = azureApiVersion;
    }
    if (provider === "openai" && organization) {
      config.organization = organization;
    }
    if (provider === "openai_compatible" && customHeaders) {
      try {
        config.custom_headers = JSON.parse(customHeaders);
      } catch {
        /* ignore parse errors */
      }
    }
    return Object.keys(config).length ? config : undefined;
  };

  const buildCapabilities = () => ({
    supports_streaming: supportsStreaming,
    supports_tool_calling: supportsToolCalling,
    supports_vision: supportsVision,
    supports_thinking: supportsThinking,
    ...(contextWindow ? { context_window: Number(contextWindow) } : {}),
  });

  const buildDefaultParams = () => {
    const params: Record<string, any> = {};
    if (temperature !== "") params.temperature = Number(temperature);
    if (maxTokens !== "") params.max_tokens = Number(maxTokens);
    if (topP !== "") params.top_p = Number(topP);
    if (supportsThinking && thinkingBudget !== "")
      params.thinking_budget = Number(thinkingBudget);
    return Object.keys(params).length ? params : undefined;
  };

  /* ---------------------------------- Handlers ---------------------------------- */

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      if (isEditMode && model) {
        const payload: ModelUpdateRequest = {
          display_name: displayName,
          description: description || null,
          provider,
          model_name: modelName,
          base_url: baseUrl || null,
          environment,
          provider_config: buildProviderConfig() ?? null,
          capabilities: buildCapabilities(),
          default_params: buildDefaultParams() ?? null,
          is_active: isActive,
        };
        if (apiKey) payload.api_key = apiKey;

        await updateMutation.mutateAsync({ id: model.id, data: payload });
        setSuccessData({ title: `Model "${displayName}" updated.` });
      } else {
        const payload: ModelCreateRequest = {
          display_name: displayName,
          description: description || null,
          provider,
          model_name: modelName,
          base_url: baseUrl || null,
          api_key: apiKey || null,
          environment,
          provider_config: buildProviderConfig() ?? null,
          capabilities: buildCapabilities(),
          default_params: buildDefaultParams() ?? null,
          is_active: isActive,
        };

        await createMutation.mutateAsync(payload);
        setSuccessData({ title: `Model "${displayName}" added to ${environment} environment.` });
      }
      onOpenChange(false);
    } catch (err: any) {
      setErrorData({
        title: isEditMode ? "Failed to update model" : "Failed to create model",
        list: [err?.message ?? String(err)],
      });
    }
  };

  const handleTestConnection = async () => {
    try {
      const result = await testMutation.mutateAsync({
        provider,
        model_name: modelName,
        base_url: baseUrl || null,
        api_key: apiKey || null,
        provider_config: buildProviderConfig() ?? null,
      });
      if (result.success) {
        setSuccessData({
          title: `Connection successful${result.latency_ms ? ` (${result.latency_ms}ms)` : ""}`,
        });
      } else {
        setErrorData({ title: "Connection failed", list: [result.message] });
      }
    } catch (err: any) {
      setErrorData({
        title: "Test connection error",
        list: [err?.message ?? String(err)],
      });
    }
  };

  const handleClose = () => onOpenChange(false);

  const isSaving = createMutation.isPending || updateMutation.isPending;
  const canTest = !!modelName && !!apiKey;

  if (!open) return null;

  /* ---------------------------------- JSX ---------------------------------- */

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-2xl max-h-[90vh] -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card shadow-lg flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex-shrink-0 border-b p-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-semibold">
                {isEditMode ? "Edit Model" : "Add Model"}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {isEditMode
                  ? "Update model configuration and settings"
                  : "Onboard a new AI model to the registry"}
              </p>
            </div>
            <button
              onClick={handleClose}
              className="rounded-sm opacity-70 transition-opacity hover:opacity-100"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Scrollable Form Body */}
        <form
          onSubmit={handleSubmit}
          className="flex-1 overflow-y-auto p-6 space-y-6"
        >
          {/* ========== BASIC INFO ========== */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Basic Information
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Display Name *</Label>
                <Input
                  required
                  placeholder="e.g., GPT-4o Production"
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

            <div>
              <Label>Description</Label>
              <Textarea
                rows={2}
                placeholder="Brief description of this model configuration"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </fieldset>

          {/* ========== CONNECTION ========== */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Connection
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Model Name / ID *</Label>
                <Input
                  required
                  placeholder="e.g., gpt-4o, claude-3-opus-20240229"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                />
              </div>
              <div>
                <Label>API Key {!isEditMode && "*"}</Label>
                <Input
                  type="password"
                  required={!isEditMode}
                  placeholder={isEditMode ? "(unchanged)" : "sk-..."}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Encrypted before storage. Never exposed in responses.
                </p>
              </div>
            </div>

            <div>
              <Label>
                Base URL
                {(provider === "azure" || provider === "openai_compatible") &&
                  " *"}
              </Label>
              <Input
                required={
                  provider === "azure" || provider === "openai_compatible"
                }
                placeholder={
                  provider === "azure"
                    ? "https://your-resource.openai.azure.com/"
                    : "https://api.example.com/v1"
                }
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
              />
            </div>

            {/* Azure-specific */}
            {provider === "azure" && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Deployment Name *</Label>
                  <Input
                    required
                    placeholder="my-gpt4-deployment"
                    value={azureDeployment}
                    onChange={(e) => setAzureDeployment(e.target.value)}
                  />
                </div>
                <div>
                  <Label>API Version</Label>
                  <Input
                    placeholder="2025-10-01-preview"
                    value={azureApiVersion}
                    onChange={(e) => setAzureApiVersion(e.target.value)}
                  />
                </div>
              </div>
            )}

            {/* OpenAI org */}
            {provider === "openai" && (
              <div>
                <Label>Organization ID</Label>
                <Input
                  placeholder="org-..."
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                />
              </div>
            )}

            {/* Custom headers */}
            {provider === "openai_compatible" && (
              <div>
                <Label>Custom Headers (JSON)</Label>
                <Textarea
                  rows={3}
                  placeholder='{"X-Custom-Header": "value"}'
                  value={customHeaders}
                  onChange={(e) => setCustomHeaders(e.target.value)}
                />
              </div>
            )}
          </fieldset>

          {/* ========== ENVIRONMENT ========== */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Environment
            </legend>
            <div className="flex gap-3">
              {ENVIRONMENTS.map((env) => (
                <button
                  key={env.value}
                  type="button"
                  onClick={() => setEnvironment(env.value)}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                    environment === env.value
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input bg-background hover:bg-muted"
                  }`}
                >
                  {env.label}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-muted-foreground">
              Models default to <strong>Test</strong>. Promote to UAT or
              Production when ready.
            </p>
          </fieldset>

          {/* ========== CAPABILITIES ========== */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Capabilities
            </legend>

            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  label: "Streaming",
                  checked: supportsStreaming,
                  onChange: setSupportsStreaming,
                },
                {
                  label: "Tool Calling",
                  checked: supportsToolCalling,
                  onChange: setSupportsToolCalling,
                },
                {
                  label: "Vision",
                  checked: supportsVision,
                  onChange: setSupportsVision,
                },
                {
                  label: "Thinking / CoT",
                  checked: supportsThinking,
                  onChange: setSupportsThinking,
                },
              ].map((cap) => (
                <label
                  key={cap.label}
                  className="flex items-center gap-2 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={cap.checked}
                    onChange={(e) => cap.onChange(e.target.checked)}
                    className="h-4 w-4 rounded border-input"
                  />
                  {cap.label}
                </label>
              ))}
            </div>

            <div>
              <Label>Context Window (tokens)</Label>
              <Input
                type="number"
                placeholder="e.g., 128000"
                value={contextWindow}
                onChange={(e) =>
                  setContextWindow(
                    e.target.value ? Number(e.target.value) : "",
                  )
                }
              />
            </div>
          </fieldset>

          {/* ========== DEFAULT PARAMS ========== */}
          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Default Parameters
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Temperature (0-2)</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  max="2"
                  placeholder="0.7"
                  value={temperature}
                  onChange={(e) =>
                    setTemperature(
                      e.target.value ? Number(e.target.value) : "",
                    )
                  }
                />
              </div>
              <div>
                <Label>Max Output Tokens</Label>
                <Input
                  type="number"
                  placeholder="4096"
                  value={maxTokens}
                  onChange={(e) =>
                    setMaxTokens(e.target.value ? Number(e.target.value) : "")
                  }
                />
              </div>
              <div>
                <Label>Top P (0-1)</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  placeholder="1.0"
                  value={topP}
                  onChange={(e) =>
                    setTopP(e.target.value ? Number(e.target.value) : "")
                  }
                />
              </div>
              {supportsThinking && (
                <div>
                  <Label>Thinking Budget</Label>
                  <Input
                    type="number"
                    placeholder="10000"
                    value={thinkingBudget}
                    onChange={(e) =>
                      setThinkingBudget(
                        e.target.value ? Number(e.target.value) : "",
                      )
                    }
                  />
                </div>
              )}
            </div>
          </fieldset>

          {/* ========== STATUS ========== */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Status
            </legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              Active
            </label>
            <p className="text-[11px] text-muted-foreground">
              Inactive models won't appear in the agent builder component
              dropdown.
            </p>
          </fieldset>
        </form>

        {/* Footer */}
        <div className="flex-shrink-0 border-t p-6">
          <div className="flex items-center gap-3">
            {/* Test Connection */}
            <Button
              type="button"
              variant="outline"
              disabled={!canTest || testMutation.isPending}
              onClick={handleTestConnection}
            >
              {testMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Zap className="mr-2 h-4 w-4" />
              )}
              Test Connection
            </Button>

            <div className="flex-1" />

            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSaving}
              onClick={handleSubmit}
            >
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditMode ? "Save Changes" : "Add Model"}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
