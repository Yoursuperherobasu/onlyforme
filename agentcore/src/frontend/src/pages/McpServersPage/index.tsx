import { useState } from "react";
import { Plus, Server, MoreVertical, Edit2, Trash2, Search } from "lucide-react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Loading from "@/components/ui/loading";
import { useDeleteMCPServer } from "@/controllers/API/queries/mcp/use-delete-mcp-server";
import { useGetMCPServer } from "@/controllers/API/queries/mcp/use-get-mcp-server";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import type { MCPServerInfoType } from "@/types/mcp";
import { cn } from "@/utils/utils";

export default function MCPServersPage() {
  const { data: servers } = useGetMCPServers();
  const { mutate: deleteServer } = useDeleteMCPServer();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [searchQuery, setSearchQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editInitialData, setEditInitialData] = useState<any>(null);
  const { mutateAsync: getServer } = useGetMCPServer();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [serverToDelete, setServerToDelete] =
    useState<MCPServerInfoType | null>(null);

  const handleEdit = async (name: string) => {
    try {
      const data = await getServer({ name });
      setEditInitialData(data);
      setEditOpen(true);
    } catch (e: any) {
      setErrorData({ title: "Error fetching server", list: [e.message] });
    }
  };

  const handleDelete = (server: MCPServerInfoType) => {
    deleteServer(
      { name: server.name },
      {
        onError: (e: any) =>
          setErrorData({ title: "Error deleting server", list: [e.message] }),
      },
    );
  };

  const openDeleteModal = (server: MCPServerInfoType) => {
    setServerToDelete(server);
    setDeleteModalOpen(true);
  };

  // Filter servers based on search
  const filteredServers = servers?.filter(
    (server) =>
      !searchQuery ||
      server.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Header - Fixed */}
      <div className="flex flex-shrink-0 items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            
            <h1 className="text-2xl font-semibold">MCP Servers</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Manage MCP Servers for use in your flows
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              placeholder="Search servers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 rounded-lg border border-border bg-card py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <Button
            variant="default"
            onClick={() => setAddOpen(true)}
            data-testid="add-mcp-server-button-page"
          >
            <Plus className="mr-2 h-4 w-4" />
            Add MCP Server
          </Button>
        </div>
      </div>

      {/* Table - Scrollable */}
      <div className="flex-1 overflow-auto p-8">
        {!servers ? (
          <div className="flex h-full w-full items-center justify-center">
            <Loading />
          </div>
        ) : filteredServers && filteredServers.length === 0 ? (
          <div className="flex h-full w-full items-center justify-center">
            <div className="text-center">
              <Server className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-semibold">No MCP servers found</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {searchQuery
                  ? "No servers match your search criteria"
                  : "Get started by adding your first MCP server"}
              </p>
              {!searchQuery && (
                <Button
                  variant="default"
                  className="mt-4"
                  onClick={() => setAddOpen(true)}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add MCP Server
                </Button>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr className="border-b border-border">
                    <th className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Server Name
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Status
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Tools
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Actions
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-border">
                  {filteredServers?.map((server) => (
                    <tr key={server.id} className="group hover:bg-muted/50">
                      {/* Server Name */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-100 dark:bg-orange-900/30">
                            <ForwardedIconComponent
                              name="Mcp"
                              className="h-5 w-5 text-orange-600 dark:text-orange-400"
                            />
                          </div>
                          <div>
                            <div className="font-semibold">{server.name}</div>
                            {server.error && (
                              <div className="mt-1 text-xs text-destructive">
                                {server.error}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {server.error ? (
                            <>
                              <span className="h-2 w-2 rounded-full bg-red-500"></span>
                              <span className="text-sm text-destructive">
                                {server.error.startsWith("Timeout")
                                  ? "Timeout"
                                  : "Error"}
                              </span>
                            </>
                          ) : server.toolsCount === null ? (
                            <>
                              <span className="h-2 w-2 animate-pulse rounded-full bg-yellow-500"></span>
                              <span className="text-sm text-muted-foreground">
                                Loading...
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="h-2 w-2 rounded-full bg-green-500"></span>
                              <span className="text-sm">Connected</span>
                            </>
                          )}
                        </div>
                      </td>

                      {/* Tools Count */}
                      <td className="px-6 py-4">
                        <ShadTooltip content={server.error || ""}>
                          <span
                            className={cn(
                              "text-sm",
                              server.error
                                ? "text-destructive"
                                : "text-muted-foreground"
                            )}
                          >
                            {server.toolsCount === null
                              ? "—"
                              : !server.toolsCount
                                ? "No tools found"
                                : `${server.toolsCount} tool${
                                    server.toolsCount === 1 ? "" : "s"
                                  }`}
                          </span>
                        </ShadTooltip>
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              className="flex h-8 w-8 items-center justify-center rounded-md opacity-0 transition-colors hover:bg-accent group-hover:opacity-100"
                              data-testid={`mcp-server-menu-button-${server.name}`}
                            >
                              <MoreVertical className="h-4 w-4 text-foreground" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => handleEdit(server.name)}
                            >
                              <Edit2 className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => openDeleteModal(server)}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-6 text-center text-sm text-muted-foreground">
              Showing {filteredServers?.length || 0} of {servers?.length || 0} servers
            </div>
          </>
        )}
      </div>

      {/* Modals */}
      <AddMcpServerModal open={addOpen} setOpen={setAddOpen} />
      {editOpen && (
        <AddMcpServerModal
          open={editOpen}
          setOpen={setEditOpen}
          initialData={editInitialData}
        />
      )}
      <DeleteConfirmationModal
        open={deleteModalOpen}
        setOpen={setDeleteModalOpen}
        onConfirm={() => {
          if (serverToDelete) handleDelete(serverToDelete);
          setDeleteModalOpen(false);
          setServerToDelete(null);
        }}
        description={"MCP Server"}
      />
    </div>
  );
}