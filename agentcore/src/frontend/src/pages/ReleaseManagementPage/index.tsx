import { Fragment, useContext, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import { Textarea } from "@/components/ui/textarea";
import { AuthContext } from "@/contexts/authContext";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  type ReleaseDetailInputPayload,
  useGetCurrentRelease,
  useGetReleaseDetails,
  useGetReleasePackages,
  useGetReleases,
  usePostBumpReleaseWithDetails,
} from "@/controllers/API/queries/releases";
import useAlertStore from "@/stores/alertStore";

type BumpType = "major" | "minor" | "patch";
type InputMode = "sheet" | "manual";

const ACTIVE_END_DATE = "9999-12-31";

const BUMP_OPTIONS: {
  value: BumpType;
  label: string;
  description: string;
  activeClasses: string;
  dot: string;
}[] = [
  {
    value: "major",
    label: "Major",
    description: "Breaking changes",
    activeClasses: "border-rose-400/50 bg-rose-500/5",
    dot: "bg-rose-500",
  },
  {
    value: "minor",
    label: "Minor",
    description: "New features",
    activeClasses: "border-amber-400/50 bg-amber-500/5",
    dot: "bg-amber-500",
  },
  {
    value: "patch",
    label: "Patch",
    description: "Bug fixes",
    activeClasses: "border-emerald-400/50 bg-emerald-500/5",
    dot: "bg-emerald-500",
  },
];

const createEmptyManualRow = (): ReleaseDetailInputPayload => ({
  section_no: undefined,
  section_title: "",
  module: "",
  sub_module: "",
  feature_capability: "",
  description_details: "",
});

/* ─── Expanded detail rows ─── */
function ExpandedReleaseDetails({ releaseId }: { releaseId: string }) {
  const { t } = useTranslation();
  const { data, isLoading } = useGetReleaseDetails({ releaseId });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loading />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <p className="py-6 text-center text-sm italic text-muted-foreground">
        {t("No detail rows attached to this release.")}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] text-sm">
        <thead>
          <tr className="border-b border-border/40">
            {["#", "Section", "Module", "Sub-Module", "Feature / Capability", "Description"].map((h) => (
              <th
                key={h}
                className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground/60"
              >
                {t(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={row.id}
              className={`border-b border-border/25 transition-colors hover:bg-muted/20 ${
                i % 2 !== 0 ? "bg-muted/10" : ""
              }`}
            >
              <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                {row.section_no ?? "—"}
              </td>
              <td className="px-4 py-2.5 text-muted-foreground">{row.section_title || "—"}</td>
              <td className="px-4 py-2.5">{row.module || "—"}</td>
              <td className="px-4 py-2.5 text-muted-foreground">{row.sub_module || "—"}</td>
              <td className="px-4 py-2.5 font-medium text-foreground">{row.feature_capability}</td>
              <td className="max-w-[200px] px-4 py-2.5 text-muted-foreground">
                <span className="line-clamp-2">{row.description_details || "—"}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExpandedReleasePackages({ releaseId }: { releaseId: string }) {
  const { t } = useTranslation();
  const [selectedService, setSelectedService] = useState("all");
  const { data, isLoading } = useGetReleasePackages({ releaseId, service: selectedService });
  const [activeTab, setActiveTab] = useState<"managed" | "transitive">("managed");
  const [searchQuery, setSearchQuery] = useState("");

  const normalizedData = useMemo(
    () =>
      (data ?? []).map((row) => ({
        ...row,
        service_name: row.service_name || "unknown",
        version: row.version || "",
        version_spec: row.version_spec || "",
        managed_roots: row.managed_roots ?? [],
        managed_root_details: row.managed_root_details ?? [],
        dependency_paths: row.dependency_paths ?? [],
      })),
    [data],
  );

  const managedPackages = normalizedData.filter((row) => row.package_type === "managed");
  const transitivePackages = normalizedData.filter((row) => row.package_type === "transitive");
  const serviceOptions = useMemo(() => {
    const values = Array.from(new Set(normalizedData.map((row) => row.service_name))).sort();
    return ["all", ...values];
  }, [normalizedData]);
  const visiblePackages = activeTab === "managed" ? managedPackages : transitivePackages;
  const filteredPackages = visiblePackages.filter((row) => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return true;
    return (
      row.name.toLowerCase().includes(q) ||
      row.service_name.toLowerCase().includes(q) ||
      row.version.toLowerCase().includes(q) ||
      row.version_spec.toLowerCase().includes(q) ||
      row.managed_roots.some((root) => root.toLowerCase().includes(q)) ||
      row.managed_root_details.some(
        (root) => root.name.toLowerCase().includes(q) || root.version.toLowerCase().includes(q),
      ) ||
      row.dependency_paths.some((path) => path.toLowerCase().includes(q))
    );
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loading />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <p className="py-6 text-center text-sm italic text-muted-foreground">
        {t("No package snapshot attached to this release.")}
      </p>
    );
  }

  return (
    <div className="px-5 py-4">
      <div className="rounded-lg border border-border/50 bg-card">
        <div className="grid grid-cols-[minmax(0,1fr)_12rem_16rem] items-center gap-3 border-b border-border/50 px-4 py-3">
          <div className="flex min-w-0 items-center gap-3 overflow-x-auto whitespace-nowrap pr-1">
            <button
              type="button"
              onClick={() => {
                setActiveTab("managed");
                setSearchQuery("");
              }}
              className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors ${
                activeTab === "managed"
                  ? "bg-background text-foreground ring-1 ring-border"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t("Managed")}
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{managedPackages.length}</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab("transitive");
                setSearchQuery("");
              }}
              className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors ${
                activeTab === "transitive"
                  ? "bg-background text-foreground ring-1 ring-border"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t("Transitive")}
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{transitivePackages.length}</span>
            </button>
          </div>
          <select
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {serviceOptions.map((serviceName) => (
              <option key={serviceName} value={serviceName}>
                {serviceName === "all" ? t("All Services") : serviceName}
              </option>
            ))}
          </select>
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={
              activeTab === "managed"
                ? t("Search managed packages...")
                : t("Search transitive packages...")
            }
            className="h-8 w-full text-sm"
          />
        </div>
        {filteredPackages.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-muted-foreground">
            {searchQuery ? t("No packages match your search.") : t("No packages found in this view.")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead>
                <tr className="border-b border-border/40 bg-muted/30 text-xs text-muted-foreground">
                  <th className="px-4 py-2.5 text-left font-semibold uppercase tracking-wider">{t("Package")}</th>
                  <th className="px-4 py-2.5 text-left font-semibold uppercase tracking-wider">{t("Service")}</th>
                  {activeTab === "managed" && (
                    <th className="px-4 py-2.5 text-left font-semibold uppercase tracking-wider">{t("Declared")}</th>
                  )}
                  <th className="px-4 py-2.5 text-left font-semibold uppercase tracking-wider">{t("Resolved")}</th>
                  {activeTab === "transitive" && (
                    <th className="px-4 py-2.5 text-left font-semibold uppercase tracking-wider">{t("Managed Root")}</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {filteredPackages.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-border/25 transition-colors hover:bg-muted/20"
                  >
                    <td className="px-4 py-2.5 font-mono text-sm">{row.name}</td>
                    <td className="px-4 py-2.5 text-sm text-muted-foreground">{row.service_name}</td>
                    {activeTab === "managed" && (
                      <td className="px-4 py-2.5 text-muted-foreground">{row.version_spec || "—"}</td>
                    )}
                    <td className="px-4 py-2.5">{row.version}</td>
                    {activeTab === "transitive" && (
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {row.managed_root_details.length > 0 ? (
                          <div className="flex flex-col gap-1 leading-tight">
                            {row.managed_root_details.slice(0, 3).map((d) => (
                              <div key={`${row.id}-${d.name}-${d.version}`}>
                                {d.name}: {d.version}
                              </div>
                            ))}
                            {row.managed_root_details.length > 3 && (
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <button
                                      type="button"
                                      className="w-fit cursor-help text-xs text-muted-foreground/80 underline decoration-dotted underline-offset-2"
                                    >
                                      +{row.managed_root_details.length - 3} more
                                    </button>
                                  </TooltipTrigger>
                                  <TooltipContent side="top" className="max-w-md">
                                    <div className="flex max-h-64 flex-col gap-1 overflow-auto text-xs">
                                      {row.managed_root_details.slice(3).map((d) => (
                                        <div key={`${row.id}-more-${d.name}-${d.version}`}>
                                          {d.name}: {d.version}
                                        </div>
                                      ))}
                                    </div>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            )}
                            {row.dependency_paths.length > 0 && (
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
                                      {row.dependency_paths.map((path, idx) => (
                                        <div key={`${row.id}-path-${idx}`}>{path}</div>
                                      ))}
                                    </div>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            )}
                          </div>
                        ) : (
                          "—"
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Small helpers ─── */
function Rule() {
  return <div className="border-t border-border/40" />;
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2.5 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground/60">
      {children}
    </p>
  );
}

/* ══════════════════════════════════════════════
   MAIN PAGE
══════════════════════════════════════════════ */
export default function ReleaseManagementPage() {
  const { t } = useTranslation();
  const { permissions } = useContext(AuthContext);
  const can = (permissionKey: string) => permissions?.includes(permissionKey);
  const canPublishRelease = can("publish_release");

  const [bumpType, setBumpType] = useState<BumpType>("patch");
  const [notes, setNotes] = useState("");
  const [inputMode, setInputMode] = useState<InputMode>("sheet");
  const [detailsFile, setDetailsFile] = useState<File | null>(null);
  const [manualRows, setManualRows] = useState<ReleaseDetailInputPayload[]>([
    createEmptyManualRow(),
  ]);
  const [expandedReleaseId, setExpandedReleaseId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const { data: currentRelease, isLoading: isLoadingCurrent } = useGetCurrentRelease();
  const { data: releases, isLoading: isLoadingHistory } = useGetReleases();
  const { mutate: bumpReleaseWithDetails, isPending: isBumping } =
    usePostBumpReleaseWithDetails();

  const isLoading = isLoadingCurrent || isLoadingHistory;
  const history = useMemo(() => releases ?? [], [releases]);

  const updateManualRow = (
    index: number,
    key: keyof ReleaseDetailInputPayload,
    value: string | number | undefined,
  ) =>
    setManualRows((prev) =>
      prev.map((row, i) => (i !== index ? row : { ...row, [key]: value })),
    );

  const removeManualRow = (index: number) =>
    setManualRows((prev) =>
      prev.length === 1 ? prev : prev.filter((_, i) => i !== index),
    );

  const handleDownloadTemplate = () => {
    const link = document.createElement("a");
    link.href = "/release_details_template.csv";
    link.download = "release_details_template.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleSelectDetailsFile = () => {
    fileInputRef.current?.click();
  };

  const handleClearDetailsFile = () => {
    setDetailsFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleCreateRelease = () => {
    if (inputMode === "sheet" && !detailsFile) {
      setErrorData({ title: t("Please upload a CSV/Excel file first.") });
      return;
    }
    const normalizedManualRows = manualRows
      .map((row) => ({
        ...row,
        section_title: row.section_title?.trim() || undefined,
        module: row.module?.trim() || undefined,
        sub_module: row.sub_module?.trim() || undefined,
        feature_capability: row.feature_capability?.trim() || "",
        description_details: row.description_details?.trim() || undefined,
      }))
      .filter((row) => row.feature_capability);

    if (inputMode === "manual" && normalizedManualRows.length === 0) {
      setErrorData({ title: t("Add at least one row with Feature / Capability.") });
      return;
    }

    bumpReleaseWithDetails(
      {
        bump_type: bumpType,
        release_notes: notes.trim() || undefined,
        details_file: inputMode === "sheet" ? detailsFile || undefined : undefined,
        manual_details: inputMode === "manual" ? normalizedManualRows : undefined,
      },
      {
        onSuccess: (res) => {
          setNotes("");
          setDetailsFile(null);
          setManualRows([createEmptyManualRow()]);
          if (fileInputRef.current) fileInputRef.current.value = "";
          setSuccessData({
            title: t("Release created: {{version}}", { version: res.version }),
          });
        },
        onError: (error: any) => {
          const message =
            error?.response?.data?.detail ||
            t("Failed to create release. Please try again.");
          setErrorData({ title: message });
        },
      },
    );
  };

  /* ── ROOT: fills whatever container the router gives it ── */
  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background">

      {/* ════════ TOP BAR ════════ */}
      <header className="flex flex-shrink-0 items-center justify-between border-b border-border/60 bg-card px-7 py-3.5">
        <div className="flex items-center gap-3">
          <div className="h-7 w-0.5 rounded-full bg-primary/60" />
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground/50">
              {t("Release Console")}
            </p>
            <h1 className="text-base font-semibold tracking-tight">{t("Release Management")}</h1>
          </div>
        </div>

        {/* Active version badge */}
        {currentRelease ? (
          <div className="flex items-center gap-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3.5 py-2">
            <span className="relative flex h-2 w-2 flex-shrink-0">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <div className="leading-tight">
              <p className="font-mono text-sm font-bold text-emerald-600">{currentRelease.version}</p>
              <p className="text-xs text-muted-foreground">
                {currentRelease.start_date} — {currentRelease.end_date}
              </p>
            </div>
            <div className="ml-2 border-l border-border/40 pl-3 text-right leading-tight">
              <p className="text-base font-bold tabular-nums">{history.length}</p>
              <p className="text-xs text-muted-foreground">{t("releases")}</p>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-border/40 bg-muted/30 px-3.5 py-2 text-sm text-muted-foreground">
            {t("No active release")}
          </div>
        )}
      </header>

      {/* ════════ BODY ════════ */}
      {isLoading ? (
        <div className="flex flex-1 items-center justify-center">
          <Loading />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 overflow-hidden">

          {/* ── LEFT SIDEBAR: Create Release ── */}
          {canPublishRelease && (
            <aside className="flex w-[320px] flex-shrink-0 flex-col overflow-y-auto border-r border-border/50 bg-card/40">

            <div className="px-5 pt-5 pb-4">
              <p className="text-sm font-semibold">{t("New Release")}</p>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {t("Select a bump, attach details, then publish.")}
              </p>
            </div>

            <Rule />

            <div className="flex flex-col gap-5 px-5 py-5">

              {/* Bump type */}
              <div>
                <Label>{t("Bump Type")}</Label>
                <div className="flex flex-col gap-1.5">
                  {BUMP_OPTIONS.map((opt) => {
                    const active = bumpType === opt.value;
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setBumpType(opt.value)}
                        className={`flex items-center justify-between rounded-md border px-3 py-2 text-left transition-all ${
                          active
                            ? `${opt.activeClasses} shadow-sm`
                            : "border-border/40 bg-background hover:border-border/70 hover:bg-muted/20"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`h-1.5 w-1.5 rounded-full transition-opacity ${opt.dot} ${
                              active ? "opacity-100" : "opacity-25"
                            }`}
                          />
                          <span className="text-sm font-semibold">{t(opt.label)}</span>
                        </div>
                        <span className="text-sm text-muted-foreground">{t(opt.description)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <Rule />

              {/* Input mode toggle */}
              <div>
                <Label>{t("Details Source")}</Label>
                <div className="flex overflow-hidden rounded-md border border-border/50 bg-background">
                  {(["sheet", "manual"] as InputMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setInputMode(mode)}
                      className={`flex-1 py-1.5 text-sm font-medium transition-all ${
                        inputMode === mode
                          ? "bg-card text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {mode === "sheet" ? t("Upload File") : t("Manual Entry")}
                    </button>
                  ))}
                </div>
              </div>

              {/* Conditional input area */}
              {inputMode === "sheet" ? (
                <div className="rounded-md border border-dashed border-border/60 bg-muted/10 p-3.5">
                  <p className="mb-2 text-xs leading-relaxed text-muted-foreground">
                    {t("Accepts .csv · .xlsx — Headers: S.No, Section, Module, Sub-Module, Feature, Description")}
                  </p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.xlsx,.xlsm,.xltx"
                    className="hidden"
                    onChange={(e) => setDetailsFile(e.target.files?.[0] || null)}
                  />
                  <div className="mt-3 flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-8 px-3 text-sm"
                      onClick={handleSelectDetailsFile}
                    >
                      {detailsFile ? t("Replace file") : t("Upload details file")}
                    </Button>
                    {detailsFile && (
                      <button
                        type="button"
                        onClick={handleClearDetailsFile}
                        className="h-8 rounded-md px-2 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                      >
                        {t("Remove")}
                      </button>
                    )}
                  </div>
                  <div className="mt-2 rounded-md border border-border/50 bg-background/80 px-2.5 py-2">
                    {detailsFile ? (
                      <p className="truncate text-sm text-foreground">{detailsFile.name}</p>
                    ) : (
                      <p className="text-sm text-muted-foreground">{t("No file selected")}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={handleDownloadTemplate}
                    className="mt-2 text-xs text-primary/70 underline-offset-2 hover:underline"
                  >
                    {t("Download blank template ↓")}
                  </button>
                </div>
              ) : (
                <p className="rounded-md border border-border/40 bg-muted/20 px-3 py-2.5 text-sm leading-relaxed text-muted-foreground">
                  {t("Fill detail rows in the table on the right. Feature / Capability is required.")}
                </p>
              )}

              <Rule />

              {/* Notes */}
              <div>
                <Label>{t("Release Notes")}</Label>
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder={t("What changed in this release?")}
                  rows={4}
                  className="resize-none text-sm"
                />
              </div>
            </div>

            {/* Publish footer — sticky at bottom of sidebar */}
            <div className="mt-auto border-t border-border/50 px-5 py-4">
              <Button
                onClick={handleCreateRelease}
                disabled={isBumping}
                size="sm"
                className="w-full text-sm"
              >
                {isBumping ? t("Publishing…") : t("Publish Release")}
              </Button>
              <p className="mt-1.5 text-center text-xs text-muted-foreground">
                {t("Bumps version and closes the active window.")}
              </p>
            </div>
            </aside>
          )}

          {/* ── RIGHT MAIN AREA ── */}
          <section className="flex min-w-0 flex-1 flex-col overflow-hidden">

            {/* Manual entry table — shown only when relevant */}
            {canPublishRelease && inputMode === "manual" && (
              <div className="flex-shrink-0 border-b border-border/50 bg-muted/5">
                <div className="flex items-center justify-between px-6 py-3">
                  <div>
                    <p className="text-sm font-semibold">{t("Detail Rows")}</p>
                    <p className="text-sm text-muted-foreground">
                      {t("Feature / Capability is required per row.")}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 px-3 text-sm"
                    onClick={() => setManualRows((prev) => [...prev, createEmptyManualRow()])}
                  >
                    + {t("Add Row")}
                  </Button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[960px]">
                    <thead>
                      <tr className="border-y border-border/40 bg-muted/30">
                        {["#", "Section", "Module", "Sub-Module", "Feature / Capability *", "Description", ""].map((h) => (
                          <th
                            key={h}
                            className="px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground/60"
                          >
                            {t(h)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/25">
                      {manualRows.map((row, index) => (
                        <tr key={`row-${index}`} className="bg-background hover:bg-muted/10">
                          <td className="w-14 px-3 py-1.5">
                            <Input
                              type="number"
                              className="h-7 w-12 text-sm"
                              value={row.section_no ?? ""}
                              onChange={(e) => {
                                const v = e.target.value;
                                updateManualRow(
                                  index,
                                  "section_no",
                                  v === "" ? undefined : Number.parseInt(v, 10),
                                );
                              }}
                            />
                          </td>
                          {(
                            [
                              "section_title",
                              "module",
                              "sub_module",
                              "feature_capability",
                              "description_details",
                            ] as (keyof ReleaseDetailInputPayload)[]
                          ).map((field) => (
                            <td key={field} className="px-3 py-1.5">
                              <Input
                                className="h-7 text-sm"
                                value={(row[field] as string) || ""}
                                onChange={(e) => updateManualRow(index, field, e.target.value)}
                              />
                            </td>
                          ))}
                          <td className="w-12 px-3 py-1.5">
                            <button
                              type="button"
                              onClick={() => removeManualRow(index)}
                              disabled={manualRows.length === 1}
                              className="rounded px-2 py-1 text-sm text-muted-foreground transition-colors hover:text-destructive disabled:opacity-30"
                            >
                              ✕
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ── Release History ── */}
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="flex flex-shrink-0 items-center justify-between border-b border-border/50 px-6 py-3.5">
                <div>
                  <p className="text-sm font-semibold">{t("Release History")}</p>
                  <p className="text-sm text-muted-foreground">
                    {t("Expand any version to inspect its attached detail rows.")}
                  </p>
                </div>
                <span className="rounded-full border border-border/40 bg-muted/30 px-2.5 py-0.5 font-mono text-sm font-medium">
                  {history.length}
                </span>
              </div>

              <div className="flex-1 overflow-y-auto">
                <table className="w-full">
                  <thead className="sticky top-0 z-10 bg-card/95 backdrop-blur-sm">
                    <tr className="border-b border-border/50">
                      {["Version", "Start Date", "End Date", "Status", "Notes", ""].map((h) => (
                        <th
                          key={h}
                          className="px-5 py-2.5 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground/60"
                        >
                          {t(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-20 text-center">
                          <p className="text-3xl">📦</p>
                          <p className="mt-3 text-sm font-medium text-muted-foreground">
                            {t("No releases yet.")}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground/60">
                            {t("Use the panel on the left to create your first release.")}
                          </p>
                        </td>
                      </tr>
                    ) : (
                      history.map((release) => {
                        const isActive = release.end_date === ACTIVE_END_DATE;
                        const isExpanded = expandedReleaseId === release.id;

                        return (
                          <Fragment key={release.id}>
                            <tr
                              className={`border-b border-border/25 transition-colors hover:bg-muted/20 ${
                                isExpanded ? "bg-muted/10" : ""
                              }`}
                            >
                              <td className="px-5 py-3">
                                <span className="font-mono text-sm font-bold">{release.version}</span>
                              </td>
                              <td className="px-5 py-3 text-sm text-muted-foreground">
                                {release.start_date}
                              </td>
                              <td className="px-5 py-3 text-sm text-muted-foreground">
                                {isActive ? (
                                  <span className="text-muted-foreground/30">—</span>
                                ) : (
                                  release.end_date
                                )}
                              </td>
                              <td className="px-5 py-3">
                                <span
                                  className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${
                                    isActive
                                      ? "bg-emerald-500/10 text-emerald-600 ring-emerald-500/20"
                                      : "bg-zinc-500/8 text-zinc-500 ring-zinc-500/15"
                                  }`}
                                >
                                  {isActive && (
                                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
                                  )}
                                  {isActive ? t("Active") : t("Closed")}
                                </span>
                              </td>
                              <td className="max-w-xs px-5 py-3">
                                <span className="line-clamp-1 text-sm text-muted-foreground">
                                  {release.release_notes || (
                                    <span className="text-muted-foreground/30">—</span>
                                  )}
                                </span>
                              </td>
                              <td className="px-5 py-3 text-right">
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedReleaseId((prev) =>
                                      prev === release.id ? null : release.id,
                                    )
                                  }
                                  className="inline-flex items-center gap-1 rounded border border-border/50 bg-background px-2.5 py-1 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                                >
                                  {isExpanded ? "↑ Hide" : "↓ Details"}
                                </button>
                              </td>
                            </tr>

                            {/* ── Expanded detail section — classy ── */}
                            {isExpanded && (
                              <tr>
                                <td colSpan={6} className="bg-card/60 px-0 py-0">
                                  {/* Header strip */}
                                  <div className="flex items-center gap-3 border-y border-border/30 bg-muted/20 px-5 py-2.5">
                                    <div className="h-3.5 w-0.5 rounded-full bg-primary/50" />
                                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground/60">
                                      {t("Detail Rows")}
                                    </p>
                                    <span className="text-xs text-muted-foreground/40">·</span>
                                    <span className="font-mono text-sm font-bold text-foreground">
                                      {release.version}
                                    </span>
                                  </div>
                                  <ExpandedReleaseDetails releaseId={release.id} />
                                  <div className="flex items-center gap-3 border-y border-border/30 bg-muted/20 px-5 py-2.5">
                                    <div className="h-3.5 w-0.5 rounded-full bg-primary/50" />
                                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground/60">
                                      {t("Package Snapshot")}
                                    </p>
                                    <span className="text-xs text-muted-foreground/40">·</span>
                                    <span className="font-mono text-sm font-bold text-foreground">
                                      {release.version}
                                    </span>
                                  </div>
                                  <ExpandedReleasePackages releaseId={release.id} />
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
