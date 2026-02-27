import { Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type GuardrailCreateOrUpdatePayload,
  type GuardrailInfo,
  usePatchGuardrailCatalogue,
  usePostGuardrailCatalogue,
} from "@/controllers/API/queries/guardrails";
import { useGetRegistryModels } from "@/controllers/API/queries/models";
import useAlertStore from "@/stores/alertStore";

interface EditGuardrailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  guardrail?: GuardrailInfo | null;
}

const CATEGORY_OPTIONS = [
  "content-safety",
  "jailbreak",
  "topic-control",
  "pii-detection",
];

const getConfigTemplate = (): string => {
  return `# models section is auto-injected from Model Registry
rails:
  input:
    flows:
      - self check input`;
};

const getPromptsTemplate = (): string => {
  return `- task: self_check_input
  content: |
    You are a safety classifier for user input.

    Block the message if it requests harmful, illegal, abusive, or violent guidance.

    User message: "{{ user_input }}"

    Should this message be blocked?
    Answer only Yes or No.
    Answer:`;
};

const pickFirstString = (
  runtimeConfig: GuardrailInfo["runtimeConfig"],
  keys: string[],
): string => {
  if (!runtimeConfig) return "";
  for (const key of keys) {
    const value = (runtimeConfig as Record<string, unknown>)[key];
    if (typeof value === "string") return value;
  }
  return "";
};

export default function EditGuardrailModal({
  open,
  onOpenChange,
  guardrail,
}: EditGuardrailModalProps) {
  const isEditMode = !!guardrail;
  const createMutation = usePostGuardrailCatalogue();
  const updateMutation = usePatchGuardrailCatalogue();

  const { data: registryModels = [], isLoading: isModelsLoading } =
    useGetRegistryModels({
      active_only: true,
    });

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [modelRegistryId, setModelRegistryId] = useState("");
  const [category, setCategory] = useState("content-safety");
  const [status, setStatus] = useState<"active" | "inactive">("active");
  const [rulesCount, setRulesCount] = useState<number | "">(0);
  const [isCustom, setIsCustom] = useState(false);

  const [configYml, setConfigYml] = useState("");
  const [promptsYml, setPromptsYml] = useState("");
  const [railsCo, setRailsCo] = useState("");
  const [preservedFiles, setPreservedFiles] = useState<Record<string, string>>();

  const selectedModel = useMemo(
    () => registryModels.find((model) => model.id === modelRegistryId) ?? null,
    [registryModels, modelRegistryId],
  );

  useEffect(() => {
    if (!open) return;
    if (registryModels.length === 0) return;

    // Legacy guardrails may not have modelRegistryId persisted.
    // Also recover if the stored model id is no longer present in active models.
    const hasValidSelection =
      !!modelRegistryId &&
      registryModels.some((model) => model.id === modelRegistryId);

    if (!hasValidSelection) {
      setModelRegistryId(registryModels[0].id);
    }
  }, [open, registryModels, modelRegistryId]);

  useEffect(() => {
    if (!open) return;

    if (guardrail) {
      setName(guardrail.name ?? "");
      setDescription(guardrail.description ?? "");
      setModelRegistryId(guardrail.modelRegistryId ?? "");
      setCategory(guardrail.category ?? "content-safety");
      setStatus((guardrail.status ?? "active") as "active" | "inactive");
      setRulesCount(
        typeof guardrail.rulesCount === "number" ? guardrail.rulesCount : 0,
      );
      setIsCustom(Boolean(guardrail.isCustom));

      const runtimeConfig = guardrail.runtimeConfig ?? undefined;
      setConfigYml(
        pickFirstString(runtimeConfig, [
          "config_yml",
          "configYml",
          "config.yml",
        ]),
      );
      setRailsCo(
        pickFirstString(runtimeConfig, ["rails_co", "railsCo", "rails.co"]),
      );
      setPromptsYml(
        pickFirstString(runtimeConfig, [
          "prompts_yml",
          "promptsYml",
          "prompts.yml",
        ]),
      );
      const files = runtimeConfig?.files;
      if (files && typeof files === "object" && !Array.isArray(files)) {
        const safeFiles = Object.fromEntries(
          Object.entries(files).filter(
            ([key, value]) => typeof key === "string" && typeof value === "string",
          ),
        ) as Record<string, string>;
        setPreservedFiles(Object.keys(safeFiles).length > 0 ? safeFiles : undefined);
      } else {
        setPreservedFiles(undefined);
      }
      return;
    }

    setName("");
    setDescription("");
    setModelRegistryId(registryModels[0]?.id ?? "");
    setCategory("content-safety");
    setStatus("active");
    setRulesCount(0);
    setIsCustom(false);
    setConfigYml(getConfigTemplate());
    setPromptsYml(getPromptsTemplate());
    setRailsCo("");
    setPreservedFiles(undefined);
  }, [guardrail, open, registryModels]);

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const buildRuntimeConfig =
    (): GuardrailCreateOrUpdatePayload["runtimeConfig"] => {
      const normalizedConfigYml = configYml.trim();
      const normalizedPromptsYml = promptsYml.trim();
      const normalizedRailsCo = railsCo.trim();
      const parsedExtraFiles =
        preservedFiles && Object.keys(preservedFiles).length > 0
          ? preservedFiles
          : undefined;

      const hasAnyRuntimeConfig =
        normalizedConfigYml !== "" ||
        normalizedPromptsYml !== "" ||
        normalizedRailsCo !== "" ||
        Boolean(parsedExtraFiles);

      if (!hasAnyRuntimeConfig) {
        return null;
      }

      return {
        config_yml: normalizedConfigYml || undefined,
        rails_co: normalizedRailsCo || undefined,
        prompts_yml: normalizedPromptsYml || undefined,
        files: parsedExtraFiles,
      };
    };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!modelRegistryId) {
      setErrorData({
        title: "Model is required",
        list: ["Please select a model from Model Registry."],
      });
      return;
    }

    if (status === "active" && configYml.trim() === "") {
      setErrorData({
        title: "config_yml is required",
        list: ["Active guardrails require config_yml. prompts_yml is optional."],
      });
      return;
    }

    let runtimeConfig: GuardrailCreateOrUpdatePayload["runtimeConfig"] = null;
    try {
      runtimeConfig = buildRuntimeConfig();
    } catch (error) {
      setErrorData({ title: "Invalid runtime config", list: [String(error)] });
      return;
    }

    const payload: GuardrailCreateOrUpdatePayload = {
      name: name.trim(),
      description: description.trim() || null,
      modelRegistryId,
      category,
      status,
      rulesCount: rulesCount === "" ? 0 : Number(rulesCount),
      isCustom,
      runtimeConfig,
      org_id: guardrail?.org_id ?? null,
      dept_id: guardrail?.dept_id ?? null,
    };

    try {
      if (isEditMode && guardrail?.id) {
        await updateMutation.mutateAsync({ id: guardrail.id, payload });
        setSuccessData({ title: `Guardrail "${payload.name}" updated.` });
      } else {
        await createMutation.mutateAsync(payload);
        setSuccessData({ title: `Guardrail "${payload.name}" created.` });
      }
      onOpenChange(false);
    } catch (error) {
      setErrorData({
        title: isEditMode
          ? "Failed to update guardrail"
          : "Failed to create guardrail",
        list: [String(error)],
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEditMode ? "Edit Guardrail" : "Add Guardrail"}
          </DialogTitle>
          <DialogDescription>
            Configure guardrail metadata and NeMo runtime files. You only need
            `config_yml` and optional `prompts_yml`. Model details and
            credentials come from Model Registry.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="guardrail-name">Name *</Label>
              <Input
                id="guardrail-name"
                required
                placeholder="NeMo Content Safety"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="guardrail-model">Model Registry Entry *</Label>
              <select
                id="guardrail-model"
                required
                value={modelRegistryId}
                onChange={(event) => setModelRegistryId(event.target.value)}
                disabled={isModelsLoading || registryModels.length === 0}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {registryModels.length === 0 ? (
                  <option value="">
                    {isModelsLoading
                      ? "Loading models..."
                      : "No active models in registry"}
                  </option>
                ) : (
                  <>
                    <option value="" disabled>
                      Select a model
                    </option>
                    {registryModels.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.display_name} ({option.provider}/
                        {option.model_name})
                      </option>
                    ))}
                  </>
                )}
              </select>
              {selectedModel && (
                <p className="text-xs text-muted-foreground">
                  Provider:{" "}
                  <span className="font-medium">{selectedModel.provider}</span>{" "}
                  | Model:{" "}
                  <span className="font-medium">
                    {selectedModel.model_name}
                  </span>
                </p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="guardrail-description">Description</Label>
            <Textarea
              id="guardrail-description"
              rows={2}
              placeholder="What this guardrail enforces"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="guardrail-category">Category *</Label>
              <select
                id="guardrail-category"
                required
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {CATEGORY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="guardrail-status">Status *</Label>
              <select
                id="guardrail-status"
                required
                value={status}
                onChange={(event) =>
                  setStatus(event.target.value as "active" | "inactive")
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="active">active</option>
                <option value="inactive">inactive</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="guardrail-rules-count">Rules Count</Label>
              <Input
                id="guardrail-rules-count"
                type="number"
                min={0}
                value={rulesCount}
                onChange={(event) => {
                  const value = event.target.value;
                  setRulesCount(value === "" ? "" : Math.max(0, Number(value)));
                }}
              />
            </div>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <input
              id="guardrail-custom"
              type="checkbox"
              checked={isCustom}
              onChange={(event) => setIsCustom(event.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            <Label htmlFor="guardrail-custom" className="text-sm">
              Mark as custom guardrail
            </Label>
          </div>

          <div className="space-y-3 rounded-md border p-4">
            <div className="text-sm font-semibold">Runtime Configuration</div>
            <p className="text-xs text-muted-foreground">
              Keep this simple: add `config_yml` and optional `prompts_yml`.
              The backend injects model settings from Model Registry. You can
              optionally customize `rails_co`; if left empty, a safe default is
              applied.
            </p>

            <div className="space-y-1.5">
              <Label htmlFor="guardrail-config-yml">config_yml</Label>
              <Textarea
                id="guardrail-config-yml"
                rows={8}
                value={configYml}
                onChange={(event) => setConfigYml(event.target.value)}
                placeholder={getConfigTemplate()}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="guardrail-rails-co">rails_co (Optional)</Label>
              <Textarea
                id="guardrail-rails-co"
                rows={8}
                value={railsCo}
                onChange={(event) => setRailsCo(event.target.value)}
                placeholder='define bot refuse to respond
  ""'
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="guardrail-prompts-yml">prompts_yml</Label>
              <Textarea
                id="guardrail-prompts-yml"
                rows={6}
                value={promptsYml}
                onChange={(event) => setPromptsYml(event.target.value)}
                placeholder={getPromptsTemplate()}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSaving || registryModels.length === 0}
            >
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditMode ? "Save Changes" : "Create Guardrail"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
