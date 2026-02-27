import {
  Search,
  Plus,
  Plug,
  Unplug,
  AlertCircle,
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
  Cloud,
} from "lucide-react";
import { useContext, useState } from "react";
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

type ProviderFilter =
  | "all"
  | "postgresql"
  | "oracle"
  | "sqlserver"
  | "mysql"
  | "azure_blob"
  | "sharepoint";

const PROVIDER_LABELS: Record<string, string> = {
  postgresql: "PostgreSQL",
  oracle: "Oracle",
  sqlserver: "SQL Server",
  mysql: "MySQL",
  azure_blob: "Azure Blob Storage",
  sharepoint: "SharePoint",
};

const PROVIDER_PORTS: Record<string, number> = {
  postgresql: 5432,
  oracle: 1521,
  sqlserver: 1433,
  mysql: 3306,
};

const DB_PROVIDERS = new Set(["postgresql", "oracle", "sqlserver", "mysql"]);
const STORAGE_PROVIDERS = new Set(["azure_blob", "sharepoint"]);
const DEFAULT_CONNECTOR_HOST =
  process.env.DEFAULT_CONNECTOR_HOST ||
  process.env.HOST_IP ||
  window.location.hostname;

function isDbProvider(provider: string): boolean {
  return DB_PROVIDERS.has(provider);
}

const BLANK_FORM = {
  name: "",
  description: "",
  provider: "postgresql",
  // DB fields
  host: DEFAULT_CONNECTOR_HOST,
  port: 5432,
  database_name: "",
  schema_name: "public",
  username: "",
  password: "",
  ssl_enabled: false,
  // Azure Blob fields
  azure_connection_string: "",
  azure_container_name: "",
  azure_blob_prefix: "",
  // SharePoint fields
  sharepoint_site_url: "",
  sharepoint_library: "Shared Documents",
  sharepoint_folder: "",
  sharepoint_client_id: "",
  sharepoint_client_secret: "",
  sharepoint_tenant_id: "",
};

type FormState = typeof BLANK_FORM;

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

  const [form, setForm] = useState<FormState>({ ...BLANK_FORM });

  const resetForm = () => {
    setForm({ ...BLANK_FORM });
    setTestResult(null);
    setShowPassword(false);
  };

  const openAddModal = () => {
    resetForm();
    setEditingConnector(null);
    setShowModal(true);
  };

  const openEditModal = (connector: ConnectorInfo) => {
    const cfg = connector.provider_config ?? {};
    setForm({
      name: connector.name,
      description: connector.description || "",
      provider: connector.provider,
      // DB fields
      host: connector.host ?? DEFAULT_CONNECTOR_HOST,
      port: connector.port ?? PROVIDER_PORTS[connector.provider] ?? 5432,
      database_name: connector.database_name ?? "",
      schema_name: connector.schema_name ?? "public",
      username: connector.username ?? "",
      password: "",
      ssl_enabled: connector.ssl_enabled,
      // Azure Blob (connection_string is masked; user must re-enter to update)
      azure_connection_string: "",
      azure_container_name: cfg.container_name ?? "",
      azure_blob_prefix: cfg.blob_prefix ?? "",
      // SharePoint (client_secret is masked; user must re-enter to update)
      sharepoint_site_url: cfg.site_url ?? "",
      sharepoint_library: cfg.library ?? "Shared Documents",
      sharepoint_folder: cfg.folder ?? "",
      sharepoint_client_id: cfg.client_id ?? "",
      sharepoint_client_secret: "",
      sharepoint_tenant_id: cfg.tenant_id ?? "",
    });
    setEditingConnector(connector);
    setTestResult(null);
    setShowModal(true);
  };

  const handleProviderChange = (provider: string) => {
    setForm((prev) => ({
      ...prev,
      provider,
      port: PROVIDER_PORTS[provider] ?? prev.port,
      schema_name:
        provider === "postgresql"
          ? "public"
          : provider === "oracle"
          ? ""
          : provider === "sqlserver"
          ? "dbo"
          : prev.schema_name,
    }));
  };

  const buildPayload = () => {
    if (form.provider === "azure_blob") {
      const provider_config: Record<string, string> = {
        container_name: form.azure_container_name,
      };
      if (form.azure_connection_string) {
        provider_config.connection_string = form.azure_connection_string;
      }
      if (form.azure_blob_prefix) {
        provider_config.blob_prefix = form.azure_blob_prefix;
      }
      return {
        name: form.name,
        description: form.description || undefined,
        provider: form.provider,
        provider_config,
      };
    }

    if (form.provider === "sharepoint") {
      const provider_config: Record<string, string> = {
        site_url: form.sharepoint_site_url,
        library: form.sharepoint_library,
        client_id: form.sharepoint_client_id,
      };
      if (form.sharepoint_tenant_id) {
        provider_config.tenant_id = form.sharepoint_tenant_id;
      }
      if (form.sharepoint_client_secret) {
        provider_config.client_secret = form.sharepoint_client_secret;
      }
      if (form.sharepoint_folder) {
        provider_config.folder = form.sharepoint_folder;
      }
      return {
        name: form.name,
        description: form.description || undefined,
        provider: form.provider,
        provider_config,
      };
    }

    // DB provider
    const payload: any = {
      name: form.name,
      description: form.description || undefined,
      provider: form.provider,
      host: form.host,
      port: form.port,
      database_name: form.database_name,
      schema_name: form.schema_name,
      username: form.username,
      ssl_enabled: form.ssl_enabled,
    };
    if (form.password) payload.password = form.password;
    return payload;
  };

  const isSaveDisabled = () => {
    if (!form.name) return true;
    if (form.provider === "azure_blob") {
      // On create, connection_string is required; on edit, container_name is always required
      if (!form.azure_container_name) return true;
      if (!editingConnector && !form.azure_connection_string) return true;
    } else if (form.provider === "sharepoint") {
      if (!form.sharepoint_site_url || !form.sharepoint_client_id) return true;
      if (!editingConnector && !form.sharepoint_client_secret) return true;
    } else {
      // DB provider
      if (!form.host || !form.database_name || !form.username) return true;
      if (!editingConnector && !form.password) return true;
    }
    return createMutation.isPending || updateMutation.isPending;
  };

  const handleSave = async () => {
    try {
      const payload = buildPayload();
      if (editingConnector) {
        await updateMutation.mutateAsync({ id: editingConnector.id, payload });
      } else {
        await createMutation.mutateAsync(payload as any);
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
      c.database_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.provider_config?.container_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.provider_config?.site_url?.toLowerCase().includes(searchQuery.toLowerCase());
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
      azure_blob: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
      sharepoint: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    };
    return styles[provider] || "bg-gray-100 text-gray-700";
  };

  const getConnectorTarget = (c: ConnectorInfo): string => {
    if (c.provider === "azure_blob") {
      return c.provider_config?.container_name ?? "—";
    }
    if (c.provider === "sharepoint") {
      return c.provider_config?.site_url ?? "—";
    }
    return c.host ? `${c.host}:${c.port}` : "—";
  };

  const getConnectorDb = (c: ConnectorInfo): string => {
    if (STORAGE_PROVIDERS.has(c.provider)) return "—";
    return c.database_name ?? "—";
  };

  const getConnectorSchema = (c: ConnectorInfo): string => {
    if (STORAGE_PROVIDERS.has(c.provider)) return "—";
    return c.schema_name ?? "—";
  };

  const FILTER_TABS: ProviderFilter[] = ["all", "postgresql", "oracle", "sqlserver", "mysql", "azure_blob", "sharepoint"];

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
            Configure and manage connections for agents (databases, Azure Blob, SharePoint)
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
              className="inline-flex items-center gap-2 rounded-lg  px-4 py-2.5 text-sm font-medium !bg-[var(--button-primary)] hover:!bg-[var(--button-primary-hover)] disabled:!bg-[var(--button-primary-disabled)] text-primary-foreground"
            >
              <Plus className="h-4 w-4" />
              Add Connector
            </button>
          )}
        </div>
      </div>

      {/* Provider filter tabs */}
      <div className="flex flex-wrap gap-2 border-b px-8 py-3">
        {FILTER_TABS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${
              filter === f
                ? "!bg-[var(--button-primary)] hover:!bg-[var(--button-primary-hover)] disabled:!bg-[var(--button-primary-disabled)] text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {f === "all" ? "All" : PROVIDER_LABELS[f] || f}
          </button>
        ))}
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
                      "Host / Container / Site",
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
                            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${getProviderBadge(c.provider)}`}
                          >
                            {STORAGE_PROVIDERS.has(c.provider) ? (
                              <Cloud className="h-3 w-3" />
                            ) : (
                              <Database className="h-3 w-3" />
                            )}
                            {PROVIDER_LABELS[c.provider] || c.provider}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm font-mono">
                            {getConnectorTarget(c)}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm">{getConnectorDb(c)}</span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm text-muted-foreground">
                            {getConnectorSchema(c)}
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
                            {STORAGE_PROVIDERS.has(c.provider)
                              ? "—"
                              : (c.tables_metadata?.length ?? "—")}
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
                                {testMutation.isPending || disconnectMutation.isPending ? (
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
                <label className="mb-1.5 block text-sm font-medium">Description</label>
                <input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  placeholder="Optional description"
                />
              </div>

              {/* Provider */}
              <div>
                <label className="mb-1.5 block text-sm font-medium">Provider</label>
                <select
                  value={form.provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  disabled={!!editingConnector}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
                >
                  <optgroup label="Databases">
                    <option value="postgresql">PostgreSQL</option>
                    <option value="oracle">Oracle</option>
                    <option value="sqlserver">SQL Server</option>
                    <option value="mysql">MySQL</option>
                  </optgroup>
                  <optgroup label="Cloud Storage">
                    <option value="azure_blob">Azure Blob Storage</option>
                    <option value="sharepoint">SharePoint</option>
                  </optgroup>
                </select>
              </div>

              {/* ── DB provider fields ── */}
              {isDbProvider(form.provider) && (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="col-span-2">
                      <label className="mb-1.5 block text-sm font-medium">Host</label>
                      <input
                        value={form.host}
                        onChange={(e) => setForm({ ...form, host: e.target.value })}
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder={DEFAULT_CONNECTOR_HOST}
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

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">Database Name</label>
                      <input
                        value={form.database_name}
                        onChange={(e) => setForm({ ...form, database_name: e.target.value })}
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="my_database"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">Schema</label>
                      <input
                        value={form.schema_name}
                        onChange={(e) => setForm({ ...form, schema_name: e.target.value })}
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="public"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">Username</label>
                      <input
                        value={form.username}
                        onChange={(e) => setForm({ ...form, username: e.target.value })}
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="db_user"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">Password</label>
                      <div className="relative">
                        <input
                          type={showPassword ? "text" : "password"}
                          value={form.password}
                          onChange={(e) => setForm({ ...form, password: e.target.value })}
                          className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-10 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                          placeholder={editingConnector ? "(unchanged)" : "password"}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  </div>

                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.ssl_enabled}
                      onChange={(e) => setForm({ ...form, ssl_enabled: e.target.checked })}
                      className="rounded border-border"
                    />
                    Enable SSL/TLS
                  </label>
                </>
              )}

              {/* ── Azure Blob fields ── */}
              {form.provider === "azure_blob" && (
                <>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">
                      Connection String{" "}
                      {editingConnector && (
                        <span className="text-xs text-muted-foreground">(leave blank to keep current)</span>
                      )}
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={form.azure_connection_string}
                        onChange={(e) =>
                          setForm({ ...form, azure_connection_string: e.target.value })
                        }
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-10 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="DefaultEndpointsProtocol=https;AccountName=..."
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">Container Name</label>
                      <input
                        value={form.azure_container_name}
                        onChange={(e) =>
                          setForm({ ...form, azure_container_name: e.target.value })
                        }
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="my-container"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">
                        Blob Prefix{" "}
                        <span className="text-xs text-muted-foreground">(optional)</span>
                      </label>
                      <input
                        value={form.azure_blob_prefix}
                        onChange={(e) =>
                          setForm({ ...form, azure_blob_prefix: e.target.value })
                        }
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="folder/subfolder/"
                      />
                    </div>
                  </div>
                </>
              )}

              {/* ── SharePoint fields ── */}
              {form.provider === "sharepoint" && (
                <>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">SharePoint Site URL</label>
                    <input
                      value={form.sharepoint_site_url}
                      onChange={(e) =>
                        setForm({ ...form, sharepoint_site_url: e.target.value })
                      }
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                      placeholder="https://contoso.sharepoint.com/sites/MySite"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">Document Library</label>
                      <input
                        value={form.sharepoint_library}
                        onChange={(e) =>
                          setForm({ ...form, sharepoint_library: e.target.value })
                        }
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="Shared Documents"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">
                        Folder Path{" "}
                        <span className="text-xs text-muted-foreground">(optional)</span>
                      </label>
                      <input
                        value={form.sharepoint_folder}
                        onChange={(e) =>
                          setForm({ ...form, sharepoint_folder: e.target.value })
                        }
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="Reports/2024"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">Client ID</label>
                      <input
                        value={form.sharepoint_client_id}
                        onChange={(e) =>
                          setForm({ ...form, sharepoint_client_id: e.target.value })
                        }
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">
                        Client Secret{" "}
                        {editingConnector && (
                          <span className="text-xs text-muted-foreground">(leave blank to keep current)</span>
                        )}
                      </label>
                      <div className="relative">
                        <input
                          type={showPassword ? "text" : "password"}
                          value={form.sharepoint_client_secret}
                          onChange={(e) =>
                            setForm({ ...form, sharepoint_client_secret: e.target.value })
                          }
                          className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-10 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                          placeholder={editingConnector ? "(unchanged)" : "client-secret"}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">Tenant ID</label>
                    <input
                      value={form.sharepoint_tenant_id}
                      onChange={(e) =>
                        setForm({ ...form, sharepoint_tenant_id: e.target.value })
                      }
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                      placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    />
                  </div>
                </>
              )}

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
                disabled={isSaveDisabled()}
                className="inline-flex items-center gap-2 rounded-lg  px-4 py-2 text-sm font-medium !bg-[var(--button-primary)] hover:!bg-[var(--button-primary-hover)] disabled:!bg-[var(--button-primary-disabled)] text-primary-foreground "
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
              Are you sure you want to delete this connector? This action cannot be undone.
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
