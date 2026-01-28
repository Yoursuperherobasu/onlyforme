import {
  Plus,
  BarChart3,
  MoreVertical,
  Edit2,
  Trash2,
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ModelType } from "@/types/models/models";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import EditModelModal from "./components/edit-model-modal";
import { getProviderIcon } from "./components/logo_provider";


interface ModelCardsViewProps {
  models: ModelType[];
  setOpenModal?: (open: boolean) => void; // optional now
  setSearch: (search: string) => void;
  onEditModel?: (model: ModelType) => void;
  onDeleteModel?: (model: ModelType) => void;
}

type ProviderType = "all" | "google" | "openai" | "anthropic" | "meta";

export default function ModelCardsView({
  models,
  setSearch,
  onEditModel,
  onDeleteModel,
}: ModelCardsViewProps): JSX.Element {
  const [filter, setFilter] = useState<ProviderType>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelType | null>(null);

  /* ---------------------------------- Dummy Models ---------------------------------- */

  const DUMMY_MODELS: ModelType[] = [
    {
      id: "1",
      name: "Gemini 2.0 Flash",
      description: "Fastest multimodal model with breakthrough speed",
      provider: "google",
      contextWindow: "1M tokens",
      pricing: "$0.10 / 1M tokens",
      category: "Multimodal",
      isCustom: false,
    },
    {
      id: "4",
      name: "GPT-4 Turbo",
      description: "Most capable GPT-4 model with vision capabilities",
      provider: "openai",
      contextWindow: "128K tokens",
      pricing: "$10 / 1M tokens",
      category: "Multimodal",
      isCustom: false,
    },
    {
      id: "8",
      name: "Claude 3 Opus",
      description: "Most powerful model for highly complex tasks",
      provider: "anthropic",
      contextWindow: "200K tokens",
      pricing: "$15 / 1M tokens",
      category: "Text",
      isCustom: false,
    },
    {
      id: "11",
      name: "Gemini 2.0 Flash",
      description: "Fastest multimodal model with breakthrough speed",
      provider: "google",
      contextWindow: "1M tokens",
      pricing: "$0.10 / 1M tokens",
      category: "Multimodal",
      isCustom: false,
    },
    {
      id: "14",
      name: "GPT-4 Turbo",
      description: "Most capable GPT-4 model with vision capabilities",
      provider: "openai",
      contextWindow: "128K tokens",
      pricing: "$10 / 1M tokens",
      category: "Multimodal",
      isCustom: false,
    },
    {
      id: "10",
      name: "Claude 3 Opus",
      description: "Most powerful model for highly complex tasks",
      provider: "anthropic",
      contextWindow: "200K tokens",
      pricing: "$15 / 1M tokens",
      category: "Text",
      isCustom: false,
    },
    {
      id: "21",
      name: "Gemini 2.0 Flash",
      description: "Fastest multimodal model with breakthrough speed",
      provider: "google",
      contextWindow: "1M tokens",
      pricing: "$0.10 / 1M tokens",
      category: "Multimodal",
      isCustom: false,
    },
    {
      id: "24",
      name: "GPT-4 Turbo",
      description: "Most capable GPT-4 model with vision capabilities",
      provider: "openai",
      contextWindow: "128K tokens",
      pricing: "$10 / 1M tokens",
      category: "Multimodal",
      isCustom: false,
    },
    {
      id: "28",
      name: "Claude 3 Opus",
      description: "Most powerful model for highly complex tasks",
      provider: "anthropic",
      contextWindow: "200K tokens",
      pricing: "$15 / 1M tokens",
      category: "Text",
      isCustom: false,
    },
  ];

  const displayModels = models?.length ? models : DUMMY_MODELS;

  /* ---------------------------------- Filtering ---------------------------------- */

  const filteredModels = displayModels.filter((model) => {
    const matchesFilter = filter === "all" || model.provider === filter;
    const matchesSearch =
      !searchQuery ||
      model.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      model.description?.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  /* ---------------------------------- Debounced Search ---------------------------------- */

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, setSearch]);

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
    ({ google: "Google", openai: "OpenAI", anthropic: "Anthropic", meta: "Meta" }[
      provider
    ] ?? provider);

  /* ---------------------------------- JSX ---------------------------------- */

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Header - Fixed */}
      <div className="flex-shrink-0 flex items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            
            <h1 className="text-2xl font-semibold">Model Catalogue</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Browse and manage AI models
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

          <Button
            onClick={() => {
              setSelectedModel(null); // create mode
              setIsEditModalOpen(true);
            }}
          >
            <Plus className="mr-2 h-4 w-4" />
            Add Custom Model
          </Button>
        </div>
      </div>

      {/* Filters - Fixed */}
      <div className="flex-shrink-0 flex gap-3 border-b px-8 py-4">
        {(["all", "google", "openai", "anthropic", "meta"] as ProviderType[]).map(
          (type) => (
            <Button
              key={type}
              variant={filter === type ? "default" : "outline"}
              onClick={() => setFilter(type)}
            >
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </Button>
          )
        )}
      </div>

      {/* Table - Scrollable */}
      <div className="flex-1 overflow-auto p-8">
        <div className="rounded-lg border bg-card overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                {[
                  "Model Name",
                  "Provider",
                  "Context",
                  "Pricing",
                  "Category",
                  "Actions",
                ].map((h) => (
                  <th key={h} className="px-6 py-4 text-left text-xs uppercase">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y">
              {filteredModels.map((model) => (
                <tr key={model.id} className="group hover:bg-muted/50">
                  <td className="px-6 py-4">
                    <div className="font-semibold">{model.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {model.description}
                    </div>
                  </td>

                  <td className="px-6 py-4 flex items-center gap-2">
                    <div className="h-8 w-8 rounded border flex items-center justify-center">
                      {getProviderLogo(model.provider)}
                    </div>
                    {getProviderName(model.provider)}
                  </td>

                  <td className="px-6 py-4 text-sm text-muted-foreground">
                    {model.contextWindow}
                  </td>

                  <td className="px-6 py-4 text-sm text-muted-foreground">
                    {model.pricing}
                  </td>

                  <td className="px-6 py-4">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            model.category === "Multimodal"
                              ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                              : model.category === "Text"
                                ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                                : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                          }`}
                        >
                          {model.category}
                        </span>
                      </td>

                  <td className="px-6 py-4">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="opacity-0 group-hover:opacity-100">
                          <MoreVertical className="h-4 w-4" />
                        </button>
                      </DropdownMenuTrigger>

                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => {
                            setSelectedModel(model);
                            setIsEditModalOpen(true);
                            onEditModel?.(model);
                          }}
                        >
                          <Edit2 className="mr-2 h-4 w-4" />
                          Configure
                        </DropdownMenuItem>

                        {model.isCustom && (
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => onDeleteModel?.(model)}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-6 text-center text-sm text-muted-foreground">
          Showing {filteredModels.length} of {displayModels.length} models
        </div>
      </div>

      {/* Modal */}
      <EditModelModal
        open={isEditModalOpen}
        onOpenChange={setIsEditModalOpen}
        model={selectedModel}
      />
    </div>
  );
}