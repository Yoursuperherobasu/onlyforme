import { memo, useCallback } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import type { APIClassType } from "@/types/api";
import SidebarItemsList from "../sidebarItemsList";
import { useTranslation } from 'react-i18next';

const SIDEBAR_CATEGORY_ACCENTS: Record<string, string> = {
  input_output: "#2563eb",
  agents: "#16a34a",
  mcp: "#0ea5e9",
  models: "#c026d3",
  vectorstores: "#ca8a04",
  processing: "#475569",
  logic: "#64748b",
  tools: "#06b6d4",
  Guardrails: "#6b7280",
  HumanInTheLoop: "#6b7280",
  outputs: "#dc2626",
  prompts: "#7c3aed",
  chains: "#f97316",
  helpers: "#0ea5e9",
};

export const CategoryDisclosure = memo(function CategoryDisclosure({
  item,
  openCategories,
  setOpenCategories,
  dataFilter,
  nodeColors,
  onDragStart,
  sensitiveSort,
}: {
  item: any;
  openCategories: string[];
  setOpenCategories;
  dataFilter: any;
  nodeColors: any;
  onDragStart: (
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType },
  ) => void;
  sensitiveSort: (a: any, b: any) => number;
}) {
  const handleKeyDownInput = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setOpenCategories((prev) =>
          prev.includes(item.name)
            ? prev.filter((cat) => cat !== item.name)
            : [...prev, item.name],
        );
      }
    },
    [item.name, setOpenCategories],
  );
  const { t } = useTranslation();
  const isOpen = openCategories.includes(item.name);
  const itemCount = Object.keys(dataFilter[item.name] ?? {}).length;
  const accentColor =
    SIDEBAR_CATEGORY_ACCENTS[item.name] ??
    nodeColors[item.name] ??
    "#2563eb";
  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      setOpenCategories((prev) =>
        isOpen ? [...prev, item.name] : prev.filter((cat) => cat !== item.name),
      );
    },
    [item.name, setOpenCategories],
  );
  return (
    <Disclosure open={isOpen} onOpenChange={handleOpenChange}>
      <SidebarMenuItem>
        <DisclosureTrigger className="group/collapsible">
          <SidebarMenuButton asChild>
            <div
              data-testid={`disclosure-${item.display_name.toLocaleLowerCase()}`}
              tabIndex={0}
              onKeyDown={handleKeyDownInput}
              className="user-select-none flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted/80"
              style={{ borderLeft: `2px solid ${accentColor}` }}
            >
              <span style={{ color: accentColor }}>
                <ForwardedIconComponent
                  name={item.icon}
                  className="h-4 w-4"
                />
              </span>
              <span
                className="flex-1 font-semibold"
                style={{ color: accentColor }}
              >
                {t(item.display_name)}
              </span>
              <span className="text-xs font-bold" style={{ color: accentColor }}>
                {itemCount}
              </span>
              <ForwardedIconComponent
                name="ChevronRight"
                className="-mr-1 h-4 w-4 text-muted-foreground transition-all group-aria-expanded/collapsible:rotate-90"
              />
            </div>
          </SidebarMenuButton>
        </DisclosureTrigger>
        <DisclosureContent>
          <SidebarItemsList
            item={item}
            dataFilter={dataFilter}
            nodeColors={nodeColors}
            onDragStart={onDragStart}
            sensitiveSort={sensitiveSort}
          />
        </DisclosureContent>
      </SidebarMenuItem>
    </Disclosure>
  );
});

CategoryDisclosure.displayName = "CategoryDisclosure";
