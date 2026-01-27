import {
  Plus,
  Search,
  Eye,
  Copy,
  Star,
  Grid3x3,
  List,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ModelType } from "@/types/models/models";
import { Button } from "@/components/ui/button";
// import EditModelModal from "./components/edit-model-modal";

interface AgentCatalogueViewProps {
  models: ModelType[];
  setOpenModal?: (open: boolean) => void;
  setSearch: (search: string) => void;
  onEditModel?: (model: ModelType) => void;
  onDeleteModel?: (model: ModelType) => void;
}

export default function AgentCatalogueView({
  models,
  setSearch,
  onEditModel,
  onDeleteModel,
}: AgentCatalogueViewProps): JSX.Element {
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelType | null>(null);

  /* ---------------------------------- Dummy Agents ---------------------------------- */

  const DUMMY_AGENTS = [
    {
      id: "1",
      name: "Customer Support Agent",
      description: "Intelligent customer support automation with context-aware responses.",
      provider: "Weaviate",
      team: "Team",
      contextWindow: "1M tokens",
      pricing: "$0.10 / 1M tokens",
      category: "Multimodal",
      status: "active",
      isCustom: false,
      rating: 4.8,
      reviews: 1240,
      tags: ["Chatbot", "AI Agent"],
      icon: "💬",
    },
    {
      id: "2",
      name: "Data Processing Pipeline",
      description: "Automated data extraction, transformation, and loading workflows.",
      provider: "Weaviate",
      team: "AI",
      contextWindow: "1M tokens",
      pricing: "$0.15 / 1M tokens",
      category: "Multimodal",
      status: "active",
      isCustom: false,
      rating: 4.6,
      reviews: 980,
      tags: ["Pipeline", "ETL"],
      icon: "🔄",
    },
    {
      id: "3",
      name: "Code Review Assistant",
      description: "AI-powered code review with security and performance insights.",
      provider: "OpenAI",
      team: "PRO",
      contextWindow: "128K tokens",
      pricing: "$10 / 1M tokens",
      category: "Text",
      status: "beta",
      isCustom: false,
      rating: 4.9,
      reviews: 667,
      tags: ["Assistant", "DevOps"],
      icon: "📝",
    },
    {
      id: "4",
      name: "Email Automation Flow",
      description: "Scalp email campaigns with personalization and A/B testing.",
      provider: "MarketingAI",
      team: "",
      contextWindow: "200K tokens",
      pricing: "$15 / 1M tokens",
      category: "Multimodal",
      status: "active",
      isCustom: false,
      rating: 4.7,
      reviews: 823,
      tags: ["Email", "Marketing"],
      icon: "💬",
    },
    {
      id: "5",
      name: "Sales Intelligence Bot",
      description: "Track leads and automate follow-ups with AI-driven insights.",
      provider: "SalesForce",
      team: "Enterprise",
      contextWindow: "500K tokens",
      pricing: "$20 / 1M tokens",
      category: "Text",
      status: "active",
      isCustom: false,
      rating: 4.5,
      reviews: 543,
      tags: ["Sales", "CRM"],
      icon: "📊",
    },
    {
      id: "6",
      name: "Document Analyzer",
      description: "Extract and analyze data from documents with high accuracy.",
      provider: "Google",
      team: "Cloud",
      contextWindow: "2M tokens",
      pricing: "$8 / 1M tokens",
      category: "Multimodal",
      status: "active",
      isCustom: false,
      rating: 4.4,
      reviews: 892,
      tags: ["Document", "AI"],
      icon: "📄",
    },
  ];

  const displayAgents = models?.length ? models : DUMMY_AGENTS;

  /* ---------------------------------- Filtering ---------------------------------- */

  const filteredAgents = displayAgents.filter((agent: any) => {
    const matchesSearch =
      !searchQuery ||
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description?.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesSearch;
  });

  /* ---------------------------------- Debounced Search ---------------------------------- */

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, setSearch]);

  /* ---------------------------------- Status Badge ---------------------------------- */

  const StatusBadge = ({ status }: { status: string }) => {
    const colors = {
      active: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
      beta: "bg-amber-500/10 text-amber-500 border-amber-500/20",
      deprecated: "bg-red-500/10 text-red-500 border-red-500/20",
    };
    return (
      <span
        className={`px-2 py-0.5 rounded text-xs font-medium border ${colors[status as keyof typeof colors] || colors.active}`}
      >
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  /* ---------------------------------- JSX ---------------------------------- */

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Header - Fixed */}
      <div className="flex-shrink-0 flex items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="text-2xl font-semibold">Agent Catalogue</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Discover and deploy pre-built AI agents and workflows. Clone, customize, and integrate into your applications.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              placeholder="Search agents"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 rounded-lg border bg-card py-2.5 pl-10 pr-4 text-sm"
            />
          </div>


          
        </div>
      </div>

      {/* Cards Grid - Scrollable */}
      <div className="flex-1 overflow-auto p-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredAgents.map((agent: any) => (
            <div
              key={agent.id}
              className="group relative border rounded-lg bg-card overflow-hidden hover:border-primary/50 transition-all"
            >
              {/* Status Badge - Top Right */}
              <div className="absolute top-4 right-4 z-10">
                <StatusBadge status={agent.status} />
              </div>

              {/* Card Content */}
              <div className="p-6">
                {/* Icon & Title */}
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-14 h-14 rounded-lg border bg-muted flex items-center justify-center text-2xl flex-shrink-0">
                    {agent.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold mb-1 truncate">
                      {agent.name}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      by {agent.provider}
                      {agent.team && (
                        <span className="ml-2 text-primary">{agent.team}</span>
                      )}
                    </p>
                  </div>
                </div>

                {/* Description */}
                <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                  {agent.description}
                </p>

                {/* Tags */}
                <div className="flex flex-wrap gap-2 mb-4">
                  {agent.tags?.map((tag: string, idx: number) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 bg-muted border rounded-md text-xs"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Rating & Actions */}
                <div className="flex items-center justify-between pt-4 border-t">
                  <div className="flex items-center gap-1.5 text-sm">
                    <Star className="h-4 w-4 fill-yellow-500 text-yellow-500" />
                    <span className="font-medium">{agent.rating}</span>
                    <span className="text-muted-foreground">
                      ({agent.reviews})
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      <Eye className="h-3.5 w-3.5 mr-1.5" />
                      View
                    </Button>
                    <Button size="sm">
                      <Copy className="h-3.5 w-3.5 mr-1.5" />
                      Copy
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 text-center text-sm text-muted-foreground">
          Showing {filteredAgents.length} of {displayAgents.length} agents
        </div>
      </div>

      {/* Modal */}
      {/* <EditModelModal
        open={isEditModalOpen}
        onOpenChange={setIsEditModalOpen}
        model={selectedModel}
      /> */}
    </div>
  );
}