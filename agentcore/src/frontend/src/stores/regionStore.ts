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

const useRegionStore = create<RegionStoreState>((set, get) => ({
  regions: [],
  selectedRegionCode: sessionStorage.getItem("selected_region") || null,
  loading: false,
  error: null,

  fetchRegions: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get<RegionInfo[]>("/api/dashboard/regions");
      const regions = response.data ?? [];
      set({ regions, loading: false });

      // If no region selected yet, default to hub region
      const current = get().selectedRegionCode;
      if (!current && regions.length > 0) {
        const hub = regions.find((r) => r.is_hub);
        const defaultCode = hub ? hub.code : regions[0].code;
        set({ selectedRegionCode: defaultCode });
        sessionStorage.setItem("selected_region", defaultCode);
      }
    } catch (e: any) {
      set({ loading: false, error: e?.message ?? "Failed to load regions" });
    }
  },

  setSelectedRegion: (code: string) => {
    set({ selectedRegionCode: code });
    sessionStorage.setItem("selected_region", code);
  },

  clearRegion: () => {
    set({ selectedRegionCode: null, regions: [] });
    sessionStorage.removeItem("selected_region");
  },
}));

export default useRegionStore;
