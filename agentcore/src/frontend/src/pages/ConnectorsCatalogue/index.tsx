import {
  Search,
  Plus,
  Plug,
  Unplug,
  AlertCircle,
  MoreVertical,
  Pencil,
  Trash2,
  Zap,
  X,
  Loader2,
  Eye,
  EyeOff,
  Cable,
  Database,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { useContext, useEffect, useState } from "react";
import Loading from "@/components/ui/loading";
import { AuthContext } from "@/contexts/authContext";
import {
  useGetConnectorCatalogue,
  type ConnectorInfo,
} from "@/controllers/API/queries/connectors/use-get-connector-catalogue";
import {
  useCreateConnector,
  useUpdateConnector,
  useDeleteConnector,
  useTestConnectorConnection,
  useDisconnectConnector,
} from "@/controllers/API/queries/connectors/use-mutate-connector";

type ProviderFilter = "all" | "postgresql" | "oracle" | "sqlserver" | "mysql";

const PROVIDER_LABELS: Record<string, string> = {
  postgresql: "PostgreSQL",
  oracle: "Oracle",
  sqlserver: "SQL Server",
  mysql: "MySQL",
};

const PROVIDER_PORTS: Record<string, number> = {
  postgresql: 5432,
  oracle: 1521,
  sqlserver: 1433,
  mysql: 3306,
};

const PROVIDER_ICONS: Record<string, typeof Database> = {
  postgresql: Database,
  oracle: Database,
  sqlserver: Database,
  mysql: Database,
};

export default function ConnectorsCatalogueView(): JSX.Element {
  const [filter, setFilter] = useState<ProviderFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editingConnector, setEditingConnector] = useState<ConnectorInfo | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const { role } = useContext(AuthContext);
  const isRoot = role === "root";

  const { data: connectors, isLoading, error } = useGetConnectorCatalogue();
  const createMutation = useCreateConnector();
  const updateMutation = useUpdateConnector();
  const deleteMutation = useDeleteConnector();
  const testMutation = useTestConnectorConnection();
  const disconnectMutation = useDisconnectConnector();

  // Form state
  const [form, setForm] = useState({
    name: "",
    description: "",
    provider: "postgresql",
    host: "localhost",
    port: 5432,
    database_name: "",
    schema_name: "public",
    username: "",
    password: "",
    ssl_enabled: false,
  });

  const resetForm = () => {
    setForm({
      name: "",
      description: "",
      provider: "postgresql",
      host: "localhost",
      port: 5432,
      database_name: "",
      schema_name: "public",
      username: "",
      password: "",
      ssl_enabled: false,
    });
    setTestResult(null);
    setShowPassword(false);
  };

  const openAddModal = () => {
    resetForm();
    setEditingConnector(null);
    setShowModal(true);
  };

  const openEditModal = (connector: ConnectorInfo) => {
    setForm({
      name: connector.name,
      description: connector.description || "",
      provider: connector.provider,
      host: connector.host,
      port: connector.port,
      database_name: connector.database_name,
      schema_name: connector.schema_name,
      username: connector.username,
      password: "",
      ssl_enabled: connector.ssl_enabled,
    });
    setEditingConnector(connector);
    setTestResult(null);
    setShowModal(true);
  };

  const handleProviderChange = (provider: string) => {
    setForm((prev) => ({
      ...prev,
      provider,
      port: PROVIDER_PORTS[provider] || prev.port,
      schema_name: provider === "postgresql" ? "public" : provider === "oracle" ? "" : "dbo",
    }));
  };

  const handleSave = async () => {
    try {
      if (editingConnector) {
        const payload: any = { ...form };
        if (!payload.password) delete payload.password;
        await updateMutation.mutateAsync({
          id: editingConnector.id,
          payload,
        });
      } else {
        await createMutation.mutateAsync(form);
      }
      setShowModal(false);
      resetForm();
    } catch (err: any) {
      console.error("Save failed:", err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      setDeleteConfirm(null);
    } catch (err: any) {
      console.error("Delete failed:", err);
    }
  };

  const handleTestConnection = async (connectorId: string) => {
    try {
      const result = await testMutation.mutateAsync(connectorId);
      setTestResult(result);
    } catch (err: any) {
      setTestResult({ success: false, message: "Test request failed" });
    }
  };

  const handleToggleConnection = async (connector: ConnectorInfo) => {
    try {
      if (connector.status === "connected") {
        await disconnectMutation.mutateAsync(connector.id);
      } else {
        await testMutation.mutateAsync(connector.id);
      }
    } catch (err: any) {
      console.error("Toggle connection failed:", err);
    }
  };

  /* ---- Filtering ---- */
  const displayConnectors = connectors ?? [];
  const filteredConnectors = displayConnectors.filter((c) => {
    const matchesFilter = filter === "all" || c.provider === filter;
    const matchesSearch =
      !searchQuery ||
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.provider.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.database_name?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  /* ---- Helpers ---- */
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "connected":
        return <Plug className="h-4 w-4 text-green-500" />;
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Unplug className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      connected: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      disconnected: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
      error: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    };
    return styles[status] || styles.disconnected;
  };

  const getProviderBadge = (provider: string) => {
    const styles: Record<string, string> = {
      postgresql: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
      oracle: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
      sqlserver: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
      mysql: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
    };
    return styles[provider] || "bg-gray-100 text-gray-700";
  };

  /* ---- JSX ---- */
  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex flex-shrink-0 items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="text-2xl font-semibold">Connectors</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Configure and manage database connections for Talk-to-Data agents
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              placeholder="Search connectors..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 rounded-lg border border-border bg-card py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          {isRoot && (
            <button
              onClick={openAddModal}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Add Connector
            </button>
          )}
        </div>
      </div>

      {/* Provider filter tabs */}
      <div className="flex gap-2 border-b px-8 py-3">
        {(["all", "postgresql", "oracle", "sqlserver", "mysql"] as ProviderFilter[]).map(
          (f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${
                filter === f
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {f === "all" ? "All" : PROVIDER_LABELS[f] || f}
            </button>
          ),
        )}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto p-8">
        {isLoading ? (
          <div className="flex h-full w-full items-center justify-center">
            <Loading />
          </div>
        ) : (
          <>
            {!!error && (
              <div className="mb-4 rounded-md border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                Failed to load connectors.
              </div>
            )}
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr className="border-b border-border">
                    {[
                      "Connector Name",
                      "Provider",
                      "Host",
                      "Database",
                      "Schema",
                      "Status",
                      "Tables",
                      ...(isRoot ? ["Actions"] : []),
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
                  {filteredConnectors.length === 0 ? (
                    <tr>
                      <td
                        colSpan={isRoot ? 8 : 7}
                        className="px-6 py-12 text-center text-muted-foreground"
                      >
                        <div className="flex flex-col items-center gap-3">
                          <Cable className="h-10 w-10 text-muted-foreground/50" />
                          <p>No connectors found</p>
                          {isRoot && (
                            <button
                              onClick={openAddModal}
                              className="text-primary hover:underline text-sm"
                            >
                              Add your first connector
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredConnectors.map((c) => (
                      <tr key={c.id} className="group hover:bg-muted/50">
                        <td className="px-6 py-4">
                          <div className="font-semibold">{c.name}</div>
                          {c.description && (
                            <div className="mt-1 text-xs text-muted-foreground">
                              {c.description}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${getProviderBadge(c.provider)}`}
                          >
                            {PROVIDER_LABELS[c.provider] || c.provider}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm font-mono">
                            {c.host}:{c.port}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm">{c.database_name}</span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm text-muted-foreground">
                            {c.schema_name}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(c.status)}
                            <span
                              className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${getStatusBadge(c.status)}`}
                            >
                              {c.status.charAt(0).toUpperCase() + c.status.slice(1)}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm font-medium">
                            {c.tables_metadata?.length ?? "—"}
                          </span>
                        </td>
                        {isRoot && (
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => handleToggleConnection(c)}
                                disabled={testMutation.isPending || disconnectMutation.isPending}
                                className={`rounded p-1.5 transition-colors ${
                                  c.status === "connected"
                                    ? "text-green-500 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20"
                                    : "text-muted-foreground hover:bg-green-50 hover:text-green-500 dark:hover:bg-green-900/20"
                                }`}
                                title={c.status === "connected" ? "Disconnect" : "Connect"}
                              >
                                {(testMutation.isPending || disconnectMutation.isPending) ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : c.status === "connected" ? (
                                  <Unplug className="h-4 w-4" />
                                ) : (
                                  <Plug className="h-4 w-4" />
                                )}
                              </button>
                              <button
                                onClick={() => handleTestConnection(c.id)}
                                disabled={testMutation.isPending}
                                className="rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                                title="Test Connection"
                              >
                                <Zap className="h-4 w-4" />
                              </button>
                              <button
                                onClick={() => openEditModal(c)}
                                className="rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                                title="Edit"
                              >
                                <Pencil className="h-4 w-4" />
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(c.id)}
                                className="rounded p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                                title="Delete"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="mt-6 text-center text-sm text-muted-foreground">
              Showing {filteredConnectors.length} of {displayConnectors.length}{" "}
              connectors
            </div>
          </>
        )}
      </div>

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-xl">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                {editingConnector ? "Edit Connector" : "Add Connector"}
              </h2>
              <button
                onClick={() => {
                  setShowModal(false);
                  resetForm();
                }}
                className="rounded p-1 hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
              {/* Name */}
              <div>
                <label className="mb-1.5 block text-sm font-medium">Name</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  placeholder="e.g., Manufacturing DB"
                />
              </div>

              {/* Description */}
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Description
                </label>
                <input
                  value={form.description}
                  onChange={(e) =>
                    setForm({ ...form, description: e.target.value })
                  }
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  placeholder="Optional description"
                />
              </div>

              {/* Provider */}
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Provider
                </label>
                <select
                  value={form.provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <option value="postgresql">PostgreSQL</option>
                  <option value="oracle">Oracle</option>
                  <option value="sqlserver">SQL Server</option>
                  <option value="mysql">MySQL</option>
                </select>
              </div>

              {/* Host + Port */}
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="mb-1.5 block text-sm font-medium">Host</label>
                  <input
                    value={form.host}
                    onChange={(e) => setForm({ ...form, host: e.target.value })}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                    placeholder="localhost"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">Port</label>
                  <input
                    type="number"
                    value={form.port}
                    onChange={(e) =>
                      setForm({ ...form, port: parseInt(e.target.value) || 0 })
                    }
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              </div>

              {/* Database + Schema */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Database Name
                  </label>
                  <input
                    value={form.database_name}
                    onChange={(e) =>
                      setForm({ ...form, database_name: e.target.value })
                    }
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                    placeholder="my_database"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Schema
                  </label>
                  <input
                    value={form.schema_name}
                    onChange={(e) =>
                      setForm({ ...form, schema_name: e.target.value })
                    }
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                    placeholder="public"
                  />
                </div>
              </div>

              {/* Username + Password */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Username
                  </label>
                  <input
                    value={form.username}
                    onChange={(e) =>
                      setForm({ ...form, username: e.target.value })
                    }
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                    placeholder="db_user"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      value={form.password}
                      onChange={(e) =>
                        setForm({ ...form, password: e.target.value })
                      }
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-10 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                      placeholder={editingConnector ? "(unchanged)" : "password"}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* SSL */}
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.ssl_enabled}
                  onChange={(e) =>
                    setForm({ ...form, ssl_enabled: e.target.checked })
                  }
                  className="rounded border-border"
                />
                Enable SSL/TLS
              </label>

              {/* Test Result */}
              {testResult && (
                <div
                  className={`flex items-center gap-2 rounded-lg px-4 py-3 text-sm ${
                    testResult.success
                      ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400"
                      : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"
                  }`}
                >
                  {testResult.success ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                  {testResult.message}
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div className="mt-6 flex justify-end gap-3 border-t pt-4">
              <button
                onClick={() => {
                  setShowModal(false);
                  resetForm();
                }}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={
                  !form.name || !form.host || !form.database_name || !form.username ||
                  (!editingConnector && !form.password) ||
                  createMutation.isPending ||
                  updateMutation.isPending
                }
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {(createMutation.isPending || updateMutation.isPending) && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                {editingConnector ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-xl border bg-card p-6 shadow-xl">
            <h3 className="mb-2 text-lg font-semibold">Delete Connector</h3>
            <p className="mb-6 text-sm text-muted-foreground">
              Are you sure you want to delete this connector? This action cannot be
              undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                disabled={deleteMutation.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50 transition-colors"
              >
                {deleteMutation.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
