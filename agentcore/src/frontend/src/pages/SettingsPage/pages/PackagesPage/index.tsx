import { useContext, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  useGetManagedPackages,
  type ManagedPackage,
} from "@/controllers/API/queries/packages/use-get-managed-packages";
import { useGetPackageServices } from "@/controllers/API/queries/packages/use-get-package-services";
import {
  useGetTransitivePackages,
  type TransitivePackage,
} from "@/controllers/API/queries/packages/use-get-transitive-packages";
import RequestPackageModal from "./components/request-package-modal";
import MyPackageRequestsModal from "./components/my-package-requests-modal";
import { AuthContext } from "@/contexts/authContext";

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

type TabKey = "managed" | "transitive";

function toServiceLabel(serviceName: string): string {
  if (serviceName === "all") return "All Services";
  return serviceName
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function InfoTooltip({ text }: { text: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="ml-1 inline-flex cursor-help">
            <ForwardedIconComponent
              name="Info"
              className="h-3.5 w-3.5 text-muted-foreground"
            />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          <p>{text}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <ForwardedIconComponent name="PackageSearch" className="mb-3 h-10 w-10 opacity-40" />
      <p className="text-sm">{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Managed table
// ---------------------------------------------------------------------------

function ManagedTable({
  packages,
  search,
  showHistoryDates,
}: {
  packages: ManagedPackage[];
  search: string;
  showHistoryDates: boolean;
}) {
  const { t } = useTranslation();

  const filtered = useMemo(() => {
    if (!search) return packages;
    const q = search.toLowerCase();
    return packages.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.service_name.toLowerCase().includes(q) ||
        p.version_spec.toLowerCase().includes(q) ||
        p.resolved_version.toLowerCase().includes(q) ||
        p.start_date.toLowerCase().includes(q) ||
        p.end_date.toLowerCase().includes(q),
    );
  }, [packages, search]);

  if (filtered.length === 0) {
    return <EmptyState message={search ? t("No packages match your search.") : t("No managed dependencies found.")} />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-muted/40 text-xs text-muted-foreground">
            <th className="px-4 py-3 text-left font-medium">{t("Package")}</th>
            <th className="px-4 py-3 text-left font-medium">{t("Service")}</th>
            <th className="px-4 py-3 text-left font-medium">{t("Declared")}</th>
            <th className="px-4 py-3 text-left font-medium">{t("Resolved")}</th>
            {showHistoryDates && (
              <th className="px-4 py-3 text-left font-medium">{t("Start Date")}</th>
            )}
            {showHistoryDates && (
              <th className="px-4 py-3 text-left font-medium">{t("End Date")}</th>
            )}
            {showHistoryDates && (
              <th className="px-4 py-3 text-left font-medium">{t("Status")}</th>
            )}
          </tr>
        </thead>
        <tbody>
          {filtered.map((pkg) => (
            <tr
              key={pkg.id}
              className="border-b last:border-0 transition-colors hover:bg-muted/30"
            >
              <td className="px-4 py-3 font-mono text-sm">{pkg.name}</td>
              <td className="px-4 py-3 text-sm">
                <Badge variant="gray" size="sm">
                  {pkg.service_name}
                </Badge>
              </td>
              <td className="px-4 py-3 text-sm text-muted-foreground">
                {pkg.version_spec || "*"}
              </td>
              <td className="px-4 py-3 text-sm">
                <Badge variant="outline" size="sm">
                  {pkg.resolved_version}
                </Badge>
              </td>
              {showHistoryDates && (
                <td className="px-4 py-3 text-sm text-muted-foreground">{pkg.start_date}</td>
              )}
              {showHistoryDates && (
                <td className="px-4 py-3 text-sm text-muted-foreground">{pkg.end_date}</td>
              )}
              {showHistoryDates && (
                <td className="px-4 py-3 text-sm whitespace-nowrap">
                  <Badge
                    variant="outline"
                    size="sm"
                    className={pkg.is_current ? "border-green-500/50 text-green-600" : ""}
                  >
                    {pkg.is_current ? t("Active Snapshot") : t("Historical Snapshot")}
                  </Badge>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t px-4 py-2 text-xs text-muted-foreground">
        {t("Showing {{count}} of {{total}} packages", {
          count: filtered.length,
          total: packages.length,
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Transitive table
// ---------------------------------------------------------------------------

function TransitiveTable({
  packages,
  search,
  showHistoryDates,
}: {
  packages: TransitivePackage[];
  search: string;
  showHistoryDates: boolean;
}) {
  const { t } = useTranslation();

  const filtered = useMemo(() => {
    if (!search) return packages;
    const q = search.toLowerCase();
    return packages.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.service_name.toLowerCase().includes(q) ||
        p.resolved_version.toLowerCase().includes(q) ||
        p.managed_roots.some((r) => r.toLowerCase().includes(q)) ||
        p.managed_root_details.some(
          (r) => r.name.toLowerCase().includes(q) || r.version.toLowerCase().includes(q),
        ) ||
        p.dependency_paths.some((path) => path.toLowerCase().includes(q)) ||
        p.start_date.toLowerCase().includes(q) ||
        p.end_date.toLowerCase().includes(q),
    );
  }, [packages, search]);

  if (filtered.length === 0) {
    return <EmptyState message={search ? t("No packages match your search.") : t("No transitive dependencies found.")} />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-muted/40 text-xs text-muted-foreground">
            <th className="px-4 py-3 text-left font-medium">{t("Package")}</th>
            <th className="px-4 py-3 text-left font-medium">{t("Service")}</th>
            <th className="px-4 py-3 text-left font-medium">{t("Version")}</th>
            <th className="px-4 py-3 text-left font-medium">{t("Managed Root")}</th>
            {showHistoryDates && (
              <th className="px-4 py-3 text-left font-medium">{t("Start Date")}</th>
            )}
            {showHistoryDates && (
              <th className="px-4 py-3 text-left font-medium">{t("End Date")}</th>
            )}
            <th className="px-4 py-3 text-left font-medium">{t("Status")}</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((pkg) => (
            <tr
              key={pkg.id}
              className="border-b last:border-0 transition-colors hover:bg-muted/30"
            >
              <td className="px-4 py-3 font-mono text-sm">{pkg.name}</td>
              <td className="px-4 py-3 text-sm">
                <Badge variant="gray" size="sm">
                  {pkg.service_name}
                </Badge>
              </td>
              <td className="px-4 py-3 text-sm">
                <Badge variant="outline" size="sm">
                  {pkg.resolved_version}
                </Badge>
              </td>
              <td className="px-4 py-3 text-sm text-muted-foreground">
                {pkg.managed_root_details.length > 0 ? (
                  <div className="flex flex-col gap-1 leading-tight">
                    {pkg.managed_root_details.slice(0, 3).map((d) => (
                      <div key={`${pkg.id}-${d.name}-${d.version}`}>
                        {d.name}: {d.version}
                      </div>
                    ))}
                    {pkg.managed_root_details.length > 3 && (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              className="w-fit cursor-help text-xs text-muted-foreground/80 underline decoration-dotted underline-offset-2"
                            >
                              +{pkg.managed_root_details.length - 3} more
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-md">
                            <div className="flex max-h-64 flex-col gap-1 overflow-auto text-xs">
                              {pkg.managed_root_details.slice(3).map((d) => (
                                <div key={`${pkg.id}-more-${d.name}-${d.version}`}>
                                  {d.name}: {d.version}
                                </div>
                              ))}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                    {pkg.dependency_paths.length > 0 && (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              className="mt-1 w-fit cursor-help text-xs text-muted-foreground/80 underline decoration-dotted underline-offset-2"
                            >
                              {t("View paths")}
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-2xl">
                            <div className="flex max-h-72 flex-col gap-1 overflow-auto text-xs">
                              {pkg.dependency_paths.map((path, idx) => (
                                <div key={`${pkg.id}-path-${idx}`}>{path}</div>
                              ))}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                  </div>
                ) : (
                  "-"
                )}
              </td>
              {showHistoryDates && (
                <td className="px-4 py-3 text-sm text-muted-foreground">{pkg.start_date}</td>
              )}
              {showHistoryDates && (
                <td className="px-4 py-3 text-sm text-muted-foreground">{pkg.end_date}</td>
              )}
              <td className="px-4 py-3 text-sm whitespace-nowrap">
                <div className="inline-flex min-w-[170px] items-center gap-1">
                  <Badge
                    variant="outline"
                    size="sm"
                    className={pkg.is_current ? "border-green-500/50 text-green-600" : ""}
                  >
                    {pkg.is_current ? t("Active Snapshot") : t("Historical Snapshot")}
                  </Badge>
                  <InfoTooltip text={t("Based on package snapshot history, not approval state.")} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t px-4 py-2 text-xs text-muted-foreground">
        {t("Showing {{count}} of {{total}} packages", {
          count: filtered.length,
          total: packages.length,
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const TABS: { key: TabKey; label: string; tooltip: string }[] = [
  {
    key: "managed",
    label: "Managed",
    tooltip:
      "Direct dependencies declared in pyproject.toml and resolved via uv.lock.",
  },
  {
    key: "transitive",
    label: "Transitive",
    tooltip:
      "Indirect dependencies pulled in automatically by your managed packages. Read-only.",
  },
];

export default function PackagesPage() {
  const { t } = useTranslation();
  const { permissions, role } = useContext(AuthContext);
  const can = (permissionKey: string) => permissions?.includes(permissionKey);
  const canRequestPackages = role !== "root" && can("request_packages");
  const [activeTab, setActiveTab] = useState<TabKey>("managed");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedService, setSelectedService] = useState("all");
  const [includeManagedHistory, setIncludeManagedHistory] = useState(false);
  const [includeHistory, setIncludeHistory] = useState(false);
  const [includeFullGraph, setIncludeFullGraph] = useState(false);
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);
  const [isMyRequestsOpen, setIsMyRequestsOpen] = useState(false);

  const { data: managedPackages, isLoading: loadingManaged } =
    useGetManagedPackages({
      include_history: includeManagedHistory,
      service: selectedService,
    });
  const { data: transitivePackages, isLoading: loadingTransitive } =
    useGetTransitivePackages({
      include_history: includeHistory,
      include_full_graph: includeFullGraph,
      service: selectedService,
    });
  const { data: services = [] } = useGetPackageServices({
    include_history: true,
  });

  const serviceOptions = useMemo(
    () => [
      { value: "all", label: toServiceLabel("all") },
      ...services.map((serviceName) => ({
        value: serviceName,
        label: toServiceLabel(serviceName),
      })),
    ],
    [services],
  );

  const isLoading =
    (activeTab === "managed" && loadingManaged) ||
    (activeTab === "transitive" && loadingTransitive);

  const counts: Record<TabKey, number> = {
    managed: (managedPackages ?? []).length,
    transitive: (transitivePackages ?? []).length,
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* ── Fixed Header ─────────────────────────────────────────── */}
      <div className="flex flex-shrink-0 flex-col gap-3 border-b px-8 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold">{t("Dependency Governance")}</h1>
          </div>
          <div className="flex items-center gap-3">
            {canRequestPackages && (
              <Button onClick={() => setIsRequestModalOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                {t("Request Package")}
              </Button>
            )}
            {role !== "root" && (
              <Button variant="outline" onClick={() => setIsMyRequestsOpen(true)}>
                {t("My Requests")}
              </Button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-1">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => {
                    setActiveTab(tab.key);
                    setSearchQuery("");
                  }}
                  className={`relative flex items-center gap-2 rounded-t-md px-4 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-background text-foreground after:absolute after:bottom-[-1px] after:left-0 after:h-[2px] after:w-full after:bg-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t(tab.label)}
                  {counts[tab.key] > 0 && (
                    <Badge variant={isActive ? "secondaryStatic" : "gray"} size="sm">
                      {counts[tab.key]}
                    </Badge>
                  )}
                  <InfoTooltip text={t(tab.tooltip)} />
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                placeholder={
                  activeTab === "managed"
                    ? t("Search managed packages...")
                    : t("Search transitive packages...")
                }
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-64 rounded-lg border border-border bg-card py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              className="h-[42px] rounded-lg border border-border bg-card px-3 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {serviceOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {t(opt.label)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <RequestPackageModal
        open={isRequestModalOpen}
        onOpenChange={setIsRequestModalOpen}
        services={services}
      />
      <MyPackageRequestsModal
        open={isMyRequestsOpen}
        onOpenChange={setIsMyRequestsOpen}
      />
      {activeTab === "transitive" && (
        <div className="flex flex-shrink-0 flex-wrap items-center justify-between gap-4 border-b bg-muted/20 px-8 py-3">
          <div className="text-xs text-muted-foreground">
            {includeFullGraph
              ? t("Scope: Full lock graph (includes optional extras)")
              : t("Scope: Managed closure (strict)")}
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <label className="flex items-center gap-2 text-xs text-foreground">
              <Switch
                checked={includeHistory}
                onCheckedChange={(checked) => setIncludeHistory(Boolean(checked))}
              />
              <span>{t("Include historical snapshots")}</span>
            </label>
            <label className="flex items-center gap-2 text-xs text-foreground">
              <Switch
                checked={includeFullGraph}
                onCheckedChange={(checked) => setIncludeFullGraph(Boolean(checked))}
              />
              <span>{t("Include optional extras / full lock graph")}</span>
            </label>
          </div>
        </div>
      )}
      {activeTab === "managed" && (
        <div className="flex flex-shrink-0 items-center justify-end gap-6 border-b bg-muted/20 px-8 py-3">
          <label className="flex items-center gap-2 text-xs text-foreground">
            <Switch
              checked={includeManagedHistory}
              onCheckedChange={(checked) => setIncludeManagedHistory(Boolean(checked))}
            />
            <span>{t("Include historical snapshots")}</span>
          </label>
        </div>
      )}

      {/* ── Scrollable Content ───────────────────────────────────── */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        {isLoading ? (
          <div className="flex h-full w-full items-center justify-center">
            <ForwardedIconComponent
              name="Loader2"
              className="h-8 w-8 animate-spin text-muted-foreground"
            />
          </div>
        ) : (
          <>
            {activeTab === "managed" && (
              <ManagedTable
                packages={managedPackages ?? []}
                search={searchQuery}
                showHistoryDates={includeManagedHistory}
              />
            )}
            {activeTab === "transitive" && (
              <TransitiveTable
                packages={transitivePackages ?? []}
                search={searchQuery}
                showHistoryDates={includeHistory}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
