import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Loading from "@/components/ui/loading";
import { useGetGuardrailsCatalogue } from "@/controllers/API/queries/guardrails/use-get-guardrails-catalogue";
import { getProviderIcon } from "@/utils/logo_provider";

interface GuardrailType {
  id: string;
  name: string;
  description: string;
  provider: string;
  category: string;
  status: "active" | "inactive";
  rulesCount: number;
  isCustom: boolean;
}

interface GuardrailsViewProps {
  guardrails?: GuardrailType[];
  setSearch?: (search: string) => void;
}

type CategoryType = "all" | "content-safety" | "jailbreak" | "topic-control" | "pii-detection";

export default function GuardrailsView({
  guardrails = [],
  setSearch = () => {},
}: GuardrailsViewProps): JSX.Element {
  const { t } = useTranslation();
  const [filter] = useState<CategoryType>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const {
    data: dbGuardrails,
    isLoading,
    error,
  } = useGetGuardrailsCatalogue();

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

  const displayGuardrails = guardrails?.length ? guardrails : (dbGuardrails ?? []);

  const filteredGuardrails = displayGuardrails.filter((guardrail) => {
    const matchesFilter = filter === "all" || guardrail.category === filter;
    const matchesSearch =
      !searchQuery ||
      guardrail.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      guardrail.description?.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, setSearch]);

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      "content-safety": t("Content Safety"),
      jailbreak: t("Jailbreak Prevention"),
      "topic-control": t("Topic Control"),
      "pii-detection": t("PII Detection"),
    };
    return labels[category] || category;
  };

  const getCategoryBadgeColor = (category: string) => {
    const colors: Record<string, string> = {
      "content-safety": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
      jailbreak: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
      "topic-control": "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
      "pii-detection": "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
    };
    return colors[category] || "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400";
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="flex flex-shrink-0 items-center justify-between border-b px-8 py-6">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="text-2xl font-semibold">{t("Guardrails Catalogue")}</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("Manage and configure AI safety guardrails")}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              placeholder={t("Search guardrails...")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 rounded-lg border border-border bg-card py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        {isLoading ? (
          <div className="flex h-full w-full items-center justify-center">
            <Loading />
          </div>
        ) : (
          <>
            {!!error && (
              <div className="mb-4 rounded-md border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {t("Failed to load guardrails from database.")}
              </div>
            )}
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr className="border-b border-border">
                    {[
                      "Guardrail Name",
                      "Provider",
                      "Category",
                      "Status",
                      "Rules",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground"
                      >
                        {t(h)}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody className="divide-y divide-border">
                  {filteredGuardrails.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-6 py-12 text-center text-muted-foreground"
                      >
                        {t("No guardrails found matching your criteria")}
                      </td>
                    </tr>
                  ) : (
                    filteredGuardrails.map((guardrail) => (
                      <tr key={guardrail.id} className="group hover:bg-muted/50">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="font-semibold">{guardrail.name}</div>
                            {guardrail.isCustom && (
                              <span className="inline-flex rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                                {t("Custom")}
                              </span>
                            )}
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {guardrail.description}
                          </div>
                        </td>

                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded border">
                              {getProviderLogo(guardrail.provider)}
                            </div>
                            <span className="text-sm">{t(guardrail.provider)}</span>
                          </div>
                        </td>

                        <td className="px-6 py-4">
                          <span
                            className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${getCategoryBadgeColor(guardrail.category)}`}
                          >
                            {getCategoryLabel(guardrail.category)}
                          </span>
                        </td>

                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={`h-2 w-2 rounded-full ${guardrail.status === "active" ? "bg-green-500" : "bg-gray-400"}`}
                            ></span>
                            <span className="text-sm capitalize">
                              {t(guardrail.status.charAt(0).toUpperCase() + guardrail.status.slice(1))}
                            </span>
                          </div>
                        </td>

                        <td className="px-6 py-4">
                          <span className="text-sm text-muted-foreground">
                            {guardrail.rulesCount} {t("rules")}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="mt-6 text-center text-sm text-muted-foreground">
              {t("Showing {{shown}} of {{total}} guardrails", {
                shown: filteredGuardrails.length,
                total: displayGuardrails.length,
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
