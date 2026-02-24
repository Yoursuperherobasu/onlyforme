import {
  Plus,
  MoreVertical,
  Edit2,
  Trash2,
  Search,
  Loader2,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { useContext, useEffect, useState } from "react";
import type { ModelType, ModelEnvironment } from "@/types/models/models";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import EditModelModal from "./components/edit-model-modal";
import RequestModelModal from "./components/request-model-modal";
import { getProviderIcon } from "@/utils/logo_provider";
import { AuthContext } from "@/contexts/authContext";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useAlertStore from "@/stores/alertStore";
import {
  useGetRegistryModels,
  useDeleteRegistryModel,
} from "@/controllers/API/queries/models";

type ProviderFilter = "all" | "openai" | "azure" | "anthropic" | "google" | "groq" | "openai_compatible";
type EnvFilter = "all" | ModelEnvironment;

const PROVIDER_LABELS: Record<string, string> = {
  all: "All",
  openai: "OpenAI",
  azure: "Azure",
  anthropic: "Anthropic",
  google: "Google",
  groq: "Groq",
  openai_compatible: "Custom",
};

const ENV_LABELS: Record<string, string> = {
  all: "All Envs",
  test: "Test",
  uat: "UAT",
  prod: "Prod",
};

const ENV_BADGE_CLASSES: Record<string, string> = {
  test: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  uat: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  prod: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
};

export default function ModelCatalogue(): JSX.Element {
  const [providerFilter, setProviderFilter] = useState<ProviderFilter>("all");
  const [envFilter, setEnvFilter] = useState<EnvFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelType | null>(null);
  const [deleteConfirmModel, setDeleteConfirmModel] = useState<ModelType | null>(null);

  const { permissions, role } = useContext(AuthContext);
  const can = (permissionKey: string) => permissions?.includes(permissionKey);
  const normalizedRole = (role ?? "").toLowerCase();
  const isModelAdmin =
    normalizedRole === "root" ||
    normalizedRole === "super_admin" ||
    normalizedRole === "department_admin";
  const canAddModel = isModelAdmin && can("add_new_model");
  const canRequestModel = can("request_new_model");

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Fetch models from API
  const { data: models, isLoading, isError } = useGetRegistryModels({
    active_only: false,
  });

  const deleteMutation = useDeleteRegistryModel();

  const displayModels = models ?? [];

  /* ---------------------------------- Filtering ---------------------------------- */

  const filteredModels = displayModels.filter((model) => {
    const matchesProvider =
      providerFilter === "all" || model.provider === providerFilter;
    const matchesEnv =
      envFilter === "all" || model.environment === envFilter;
    const matchesSearch =
      !searchQuery ||
      model.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      model.model_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      model.description?.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesProvider && matchesEnv && matchesSearch;
  });

  /* ---------------------------------- Helpers ---------------------------------- */

  const getProviderLogo = (provider: string) => {
    const iconSrc = getProviderIcon(provider);
    return (
      <img
        src={iconSrc}
        alt={`${provider} icon`}
        className="h-4 w-4 object-contain"
      />
    );
  };

  const getProviderName = (provider: string) =>
    PROVIDER_LABELS[provider] ?? provider;

  const handleDeleteConfirm = async () => {
    if (!deleteConfirmModel) return;
    try {
      await deleteMutation.mutateAsync({ id: deleteConfirmModel.id });
      setSuccessData({ title: `Model "${deleteConfirmModel.display_name}" deleted.` });
    } catch {
      setErrorData({ title: "Failed to delete model." });
    }
    setDeleteConfirmModel(null);
  };

  /* ---------------------------------- Capabilities badges ---------------------------------- */

  const capabilityBadges = (model: ModelType) => {
    const caps = model.capabilities;
    if (!caps) return null;
    const badges: string[] = [];
    if (caps.supports_streaming) badges.push("Streaming");
    if (caps.supports_tool_calling) badges.push("Tools");
    if (caps.supports_vision) badges.push("Vision");
    if (caps.supports_thinking) badges.push("Thinking");
    if (caps.context_window) badges.push(`${(caps.context_window / 1000).toFixed(0)}K ctx`);
    return badges;
  };

  /* ---------------------------------- JSX ---------------------------------- */

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="text-2xl font-semibold">Model Registry</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Onboard, browse, and manage AI models across environments
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              placeholder="Search models..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 rounded-lg border bg-card py-2.5 pl-10 pr-4 text-sm"
            />
          </div>

          {canAddModel ? (
            <ShadTooltip
              content={
                !canAddModel
                  ? "You don't have permission to add models"
                  : ""
              }
            >
              <span className="inline-block">
                <Button
                  onClick={() => {
                    setSelectedModel(null);
                    setIsEditModalOpen(true);
                  }}
                  disabled={!canAddModel}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add Model
                </Button>
              </span>
            </ShadTooltip>
          ) : canRequestModel ? (
            <Button onClick={() => setIsRequestModalOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Request New Model
            </Button>
          ) : null}
        </div>
      </div>

      {/* Filters */}
      <div className="flex-shrink-0 flex items-center gap-6 border-b px-8 py-4">
        {/* Provider filter */}
        <div className="flex gap-2">
          {(Object.keys(PROVIDER_LABELS) as ProviderFilter[]).map((type) => (
            <Button
              key={type}
              size="sm"
              variant={providerFilter === type ? "default" : "outline"}
              onClick={() => setProviderFilter(type)}
            >
              {PROVIDER_LABELS[type]}
            </Button>
          ))}
        </div>

        <div className="h-6 w-px bg-border" />

        {/* Environment filter */}
        <div className="flex gap-2">
          {(Object.keys(ENV_LABELS) as EnvFilter[]).map((env) => (
            <Button
              key={env}
              size="sm"
              variant={envFilter === env ? "default" : "outline"}
              onClick={() => setEnvFilter(env)}
            >
              {ENV_LABELS[env]}
            </Button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto p-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center py-20 text-destructive">
            Failed to load models. Please try again.
          </div>
        ) : (
          <>
            <div className="rounded-lg border bg-card overflow-x-auto">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    {[
                      "Model",
                      "Provider",
                      "Model ID",
                      "Environment",
                      "Capabilities",
                      "Status",
                      "Actions",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody className="divide-y">
                  {filteredModels.length === 0 ? (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-6 py-12 text-center text-sm text-muted-foreground"
                      >
                        {displayModels.length === 0
                          ? "No models onboarded yet. Click 'Add Model' to get started."
                          : "No models match the current filters."}
                      </td>
                    </tr>
                  ) : (
                    filteredModels.map((model) => (
                      <tr key={model.id} className="group hover:bg-muted/50">
                        {/* Model Name */}
                        <td className="px-6 py-4">
                          <div className="font-semibold">
                            {model.display_name}
                          </div>
                          {model.description && (
                            <div className="mt-0.5 text-xs text-muted-foreground line-clamp-1">
                              {model.description}
                            </div>
                          )}
                        </td>

                        {/* Provider */}
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded border">
                              {getProviderLogo(model.provider)}
                            </div>
                            <span className="text-sm">
                              {getProviderName(model.provider)}
                            </span>
                          </div>
                        </td>

                        {/* Model ID */}
                        <td className="px-6 py-4 text-sm font-mono text-muted-foreground">
                          {model.model_name}
                        </td>

                        {/* Environment */}
                        <td className="px-6 py-4">
                          <span
                            className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium uppercase ${
                              ENV_BADGE_CLASSES[model.environment] ?? "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {model.environment}
                          </span>
                        </td>

                        {/* Capabilities */}
                        <td className="px-6 py-4">
                          <div className="flex flex-wrap gap-1">
                            {capabilityBadges(model)?.map((badge) => (
                              <span
                                key={badge}
                                className="inline-flex rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium"
                              >
                                {badge}
                              </span>
                            ))}
                          </div>
                        </td>

                        {/* Status */}
                        <td className="px-6 py-4">
                          {model.is_active ? (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600">
                              <CheckCircle className="h-3.5 w-3.5" />
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
                              <XCircle className="h-3.5 w-3.5" />
                              Inactive
                            </span>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="px-6 py-4">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <button className="opacity-0 group-hover:opacity-100 transition-opacity">
                                <MoreVertical className="h-4 w-4" />
                              </button>
                            </DropdownMenuTrigger>

                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => {
                                  setSelectedModel(model);
                                  setIsEditModalOpen(true);
                                }}
                              >
                                <Edit2 className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>

                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() => setDeleteConfirmModel(model)}
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="mt-6 text-center text-sm text-muted-foreground">
              Showing {filteredModels.length} of {displayModels.length} models
            </div>
          </>
        )}
      </div>

      {/* Edit/Create Modal */}
      <EditModelModal
        open={isEditModalOpen}
        onOpenChange={setIsEditModalOpen}
        model={selectedModel}
      />
      <RequestModelModal
        open={isRequestModalOpen}
        onOpenChange={setIsRequestModalOpen}
      />

      {/* Delete Confirmation Dialog */}
      {deleteConfirmModel && (
        <>
          <div
            className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm"
            onClick={() => setDeleteConfirmModel(null)}
          />
          <div className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg">
            <h3 className="text-lg font-semibold">Delete Model</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to delete{" "}
              <strong>{deleteConfirmModel.display_name}</strong>? This action
              cannot be undone.
            </p>
            <div className="mt-6 flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setDeleteConfirmModel(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                className="flex-1"
                onClick={handleDeleteConfirm}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                Delete
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
