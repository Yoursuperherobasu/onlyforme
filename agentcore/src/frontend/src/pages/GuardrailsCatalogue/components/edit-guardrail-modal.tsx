import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type GuardrailCreateOrUpdatePayload,
  type GuardrailInfo,
  usePatchGuardrailCatalogue,
  usePostGuardrailCatalogue,
} from "@/controllers/API/queries/guardrails";
import useAlertStore from "@/stores/alertStore";

interface EditGuardrailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  guardrail?: GuardrailInfo | null;
}

const PROVIDER_OPTIONS = ["NVIDIA", "OpenAI", "Groq", "Google", "Azure", "Anthropic", "Custom"];
const CATEGORY_OPTIONS = ["content-safety", "jailbreak", "topic-control", "pii-detection"];

const getConfigTemplate = (selectedProvider: string): string => {
  const normalized = selectedProvider.trim().toLowerCase();

  if (normalized === "groq") {
    return `models:
  - type: main
    engine: groq
    model: llama-3.1-8b-instant`;
  }

  if (normalized === "google") {
    return `models:
  - type: main
    engine: google_genai
    model: gemini-1.5-flash`;
  }

  if (normalized === "openai") {
    return `models:
  - type: main
    engine: openai
    model: gpt-4o-mini`;
  }

  return `models:
  - type: main
    engine: <provider_engine>
    model: <model_name>`;
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

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [provider, setProvider] = useState("NVIDIA");
  const [category, setCategory] = useState("content-safety");
  const [status, setStatus] = useState<"active" | "inactive">("active");
  const [rulesCount, setRulesCount] = useState<number | "">(0);
  const [isCustom, setIsCustom] = useState(false);

  const [configYml, setConfigYml] = useState("");
  const [railsCo, setRailsCo] = useState("");
  const [promptsYml, setPromptsYml] = useState("");
  const [extraFiles, setExtraFiles] = useState("{}");

  useEffect(() => {
    if (!open) return;

    if (guardrail) {
      setName(guardrail.name ?? "");
      setDescription(guardrail.description ?? "");
      setProvider(guardrail.provider ?? "NVIDIA");
      setCategory(guardrail.category ?? "content-safety");
      setStatus((guardrail.status ?? "active") as "active" | "inactive");
      setRulesCount(typeof guardrail.rulesCount === "number" ? guardrail.rulesCount : 0);
      setIsCustom(Boolean(guardrail.isCustom));

      const runtimeConfig = guardrail.runtimeConfig ?? undefined;
      setConfigYml(pickFirstString(runtimeConfig, ["config_yml", "configYml", "config.yml"]));
      setRailsCo(pickFirstString(runtimeConfig, ["rails_co", "railsCo", "rails.co"]));
      setPromptsYml(pickFirstString(runtimeConfig, ["prompts_yml", "promptsYml", "prompts.yml"]));
      const files = runtimeConfig?.files;
      setExtraFiles(files ? JSON.stringify(files, null, 2) : "{}");
      return;
    }

    setName("");
    setDescription("");
    setProvider("NVIDIA");
    setCategory("content-safety");
    setStatus("active");
    setRulesCount(0);
    setIsCustom(false);
    setConfigYml("");
    setRailsCo("");
    setPromptsYml("");
    setExtraFiles("{}");
  }, [guardrail, open]);

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const buildRuntimeConfig = (): GuardrailCreateOrUpdatePayload["runtimeConfig"] => {
    const normalizedConfigYml = configYml.trim();
    const normalizedRailsCo = railsCo.trim();
    const normalizedPromptsYml = promptsYml.trim();
    const normalizedExtraFiles = extraFiles.trim();

    let parsedExtraFiles: Record<string, string> | undefined;
    if (normalizedExtraFiles && normalizedExtraFiles !== "{}") {
      let parsed: unknown;
      try {
        parsed = JSON.parse(normalizedExtraFiles);
      } catch {
        throw new Error("Extra runtime files must be valid JSON.");
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Extra runtime files must be a JSON object.");
      }
      const invalidEntry = Object.entries(parsed as Record<string, unknown>).find(
        ([key, value]) => typeof key !== "string" || typeof value !== "string",
      );
      if (invalidEntry) {
        throw new Error("Extra runtime files must map string paths to string content.");
      }
      parsedExtraFiles = parsed as Record<string, string>;
    }

    const hasAnyRuntimeConfig =
      normalizedConfigYml !== "" ||
      normalizedRailsCo !== "" ||
      normalizedPromptsYml !== "" ||
      Boolean(parsedExtraFiles && Object.keys(parsedExtraFiles).length > 0);

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
      provider,
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
        title: isEditMode ? "Failed to update guardrail" : "Failed to create guardrail",
        list: [String(error)],
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditMode ? "Edit Guardrail" : "Add Guardrail"}</DialogTitle>
          <DialogDescription>
            Configure guardrail metadata and optional NeMo runtime configuration files.
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
              <Label htmlFor="guardrail-provider">Provider *</Label>
              <select
                id="guardrail-provider"
                required
                value={provider}
                onChange={(event) => setProvider(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {PROVIDER_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
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
                onChange={(event) => setStatus(event.target.value as "active" | "inactive")}
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
            <div className="text-sm font-semibold">Runtime Configuration (Optional)</div>
            <p className="text-xs text-muted-foreground">
              Use these fields to store NeMo runtime files. The backend expects `config_yml` and `rails_co`
              for execution. For auth, set provider keys in backend env (for example `GROQ_API_KEY` or
              `GOOGLE_API_KEY` / `GEMINI_API_KEY`).
            </p>

            <div className="space-y-1.5">
              <Label htmlFor="guardrail-config-yml">config_yml</Label>
              <Textarea
                id="guardrail-config-yml"
                rows={8}
                value={configYml}
                onChange={(event) => setConfigYml(event.target.value)}
                placeholder={getConfigTemplate(provider)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="guardrail-rails-co">rails_co</Label>
              <Textarea
                id="guardrail-rails-co"
                rows={8}
                value={railsCo}
                onChange={(event) => setRailsCo(event.target.value)}
                placeholder="define flow self check input
  user ...
  bot refuse"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="guardrail-prompts-yml">prompts_yml</Label>
              <Textarea
                id="guardrail-prompts-yml"
                rows={6}
                value={promptsYml}
                onChange={(event) => setPromptsYml(event.target.value)}
                placeholder="- task: self_check_input
  content: |-
    ..."
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="guardrail-extra-files">Extra files JSON (`files`)</Label>
              <Textarea
                id="guardrail-extra-files"
                rows={4}
                value={extraFiles}
                onChange={(event) => setExtraFiles(event.target.value)}
                placeholder='{"policies/company.co": "define flow ..."}'
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditMode ? "Save Changes" : "Create Guardrail"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
