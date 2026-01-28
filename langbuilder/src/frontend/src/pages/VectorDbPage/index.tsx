import {
  Plus,
  Database,
  MoreVertical,
  Edit2,
  Trash2,
  Search,
  Settings,
  Activity,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { getProviderIcon } from "@/utils/logo_provider";

interface VectorDBType {
  id: string;
  name: string;
  description: string;
  provider: string;
  deployment: "SaaS" | "Self-hosted" | "Hybrid";
  dimensions: string;
  indexType: string;
  status: "connected" | "disconnected" | "configuring";
  vectorCount: string;
  isCustom: boolean;
}

interface VectorDBViewProps {
  vectorDBs: VectorDBType[];
  setSearch: (search: string) => void;
  onEditVectorDB?: (vectorDB: VectorDBType) => void;
  onDeleteVectorDB?: (vectorDB: VectorDBType) => void;
  onConfigureVectorDB?: (vectorDB: VectorDBType) => void;
}

type DeploymentType = "all" | "saas" | "self-hosted" | "hybrid";

export default function VectorDBView({
  vectorDBs,
  setSearch,
  onEditVectorDB,
  onDeleteVectorDB,
  onConfigureVectorDB,
}: VectorDBViewProps): JSX.Element {
  const [filter, setFilter] = useState<DeploymentType>("all");
  const [searchQuery, setSearchQuery] = useState("");


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

  /* ---------------------------------- Dummy Vector DBs ---------------------------------- */

  const DUMMY_VECTOR_DBS: VectorDBType[] = [
    {
      id: "1",
      name: "Pinecone (Azure SaaS)",
      description: "Fully managed vector database from Pinecone.",
      provider: "Pinecone",
      deployment: "SaaS",
      dimensions: "1536",
      indexType: "HNSW",
      status: "connected",
      vectorCount: "2.4M",
      isCustom: false,
    },
    
  ];

  const displayVectorDBs = vectorDBs?.length ? vectorDBs : DUMMY_VECTOR_DBS;

  /* ---------------------------------- Filtering ---------------------------------- */

  const filteredVectorDBs = displayVectorDBs.filter((db) => {
    const matchesFilter =
      filter === "all" ||
      db.deployment.toLowerCase().replace("-", "") === filter.replace("-", "");
    const matchesSearch =
      !searchQuery ||
      db.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      db.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      db.provider.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  /* ---------------------------------- Debounced Search ---------------------------------- */

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, setSearch]);

  /* ---------------------------------- Helpers ---------------------------------- */



  const getDeploymentBadgeColor = (deployment: string) => {
    const colors: Record<string, string> = {
      SaaS: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
      "Self-hosted":
        "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
      Hybrid:
        "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
    };
    return (
      colors[deployment] ||
      "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400"
    );
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      connected: "bg-green-500",
      disconnected: "bg-red-500",
      configuring: "bg-yellow-500",
    };
    return colors[status] || "bg-gray-400";
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      connected: "Connected",
      disconnected: "Disconnected",
      configuring: "Configuring",
    };
    return labels[status] || status;
  };

  /* ---------------------------------- JSX ---------------------------------- */

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Header - Fixed */}
      <div className="flex flex-shrink-0 items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <Database className="h-7 w-7 text-purple-500" />
            <h1 className="text-2xl font-semibold">Vector Database Catalogue</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Manage and configure vector database connections
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              placeholder="Search vector databases..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 rounded-lg border border-border bg-card py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <Button variant="default">
            <Plus className="mr-2 h-4 w-4" />
            Add Vector Database
          </Button>
        </div>
      </div>

     

      {/* Table - Scrollable */}
      <div className="flex-1 overflow-auto p-8">
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr className="border-b border-border">
                {[
                  "Database Name",
                  "Provider",
                  "Deployment",
                  "Dimensions",
                  "Index Type",
                  "Status",
                  "Vectors",
                  
                ].map((h) => (
                  <th
                    key={h}
                    className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-border">
              {filteredVectorDBs.length === 0 ? (
                <tr>
                  <td
                    colSpan={9}
                    className="px-6 py-12 text-center text-muted-foreground"
                  >
                    No vector databases found matching your criteria
                  </td>
                </tr>
              ) : (
                filteredVectorDBs.map((db) => (
                  <tr key={db.id} className="group hover:bg-muted/50">
                    {/* Database Name */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="font-semibold">{db.name}</div>
                        {db.isCustom && (
                          <span className="inline-flex rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                            Custom
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {db.description}
                      </div>
                    </td>

                    {/* Provider */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="h-8 w-8 rounded border flex items-center justify-center">
                        {getProviderLogo(db.provider)}
                        </div>
                        <span className="text-sm">{db.provider}</span>
                      </div>
                    </td>

                    {/* Deployment */}
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${getDeploymentBadgeColor(db.deployment)}`}
                      >
                        {db.deployment}
                      </span>
                    </td>

                    {/* Dimensions */}
                    <td className="px-6 py-4">
                      <span className="text-sm text-muted-foreground">
                        {db.dimensions}
                      </span>
                    </td>

                    {/* Index Type */}
                    <td className="px-6 py-4">
                      <span className="text-sm font-mono text-muted-foreground">
                        {db.indexType}
                      </span>
                    </td>

                    
                     {/* Status */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-2 w-2 rounded-full ${getStatusColor(db.status)}`}
                        ></span>
                        <span className="text-sm">
                          {getStatusLabel(db.status)}
                        </span>
                      </div>
                    </td>

                    {/* Vector Count */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1">
                        <Activity className="h-3 w-3 text-muted-foreground" />
                        <span className="text-sm font-medium">
                          {db.vectorCount}
                        </span>
                      </div>
                    </td>

            
                    
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-6 text-center text-sm text-muted-foreground">
          Showing {filteredVectorDBs.length} of {displayVectorDBs.length} vector
          databases
        </div>
      </div>
    </div>
  );
}