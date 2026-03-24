import { create } from "zustand";
import { api } from "@/controllers/API/api";

export type RegionInfo = {
  code: string;
  name: string;
  is_hub: boolean;
};

type RegionStoreState = {
  regions: RegionInfo[];
  selectedRegionCode: string | null;
  loading: boolean;
  error: string | null;

  fetchRegions: () => Promise<void>;
  setSelectedRegion: (code: string) => void;
  clearRegion: () => void;
};

const normalizeRegionCode = (code: string | null | undefined) => {
  const trimmedCode = code?.trim() ?? "";
  return trimmedCode.length > 0 ? trimmedCode : null;
};

const sanitizeRegions = (regions: RegionInfo[]) =>
  regions
    .map((region) => {
      const code = normalizeRegionCode(region.code);
      if (!code) return null;

      return {
        ...region,
        code,
        name: region.name?.trim() || code,
      };
    })
    .filter((region): region is RegionInfo => region !== null);

const useRegionStore = create<RegionStoreState>((set, get) => ({
  regions: [],
  selectedRegionCode: normalizeRegionCode(sessionStorage.getItem("selected_region")),
  loading: false,
  error: null,

  fetchRegions: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get<RegionInfo[]>("/api/dashboard/regions");
      const regions = sanitizeRegions(response.data ?? []);
      const current = get().selectedRegionCode;
      const hasCurrentRegion = !!current && regions.some((region) => region.code === current);
      const nextSelectedRegionCode = hasCurrentRegion
        ? current
        : regions.length > 0
          ? (regions.find((r) => r.is_hub)?.code ?? regions[0].code)
          : null;

      set({ regions, selectedRegionCode: nextSelectedRegionCode, loading: false });

      if (nextSelectedRegionCode) {
        sessionStorage.setItem("selected_region", nextSelectedRegionCode);
      } else {
        sessionStorage.removeItem("selected_region");
      }
    } catch (e: any) {
      set({ loading: false, error: e?.message ?? "Failed to load regions" });
    }
  },

  setSelectedRegion: (code: string) => {
    const normalizedCode = normalizeRegionCode(code);
    set({ selectedRegionCode: normalizedCode });

    if (normalizedCode) {
      sessionStorage.setItem("selected_region", normalizedCode);
    } else {
      sessionStorage.removeItem("selected_region");
    }
  },

  clearRegion: () => {
    set({ selectedRegionCode: null, regions: [] });
    sessionStorage.removeItem("selected_region");
  },
}));

export default useRegionStore;
