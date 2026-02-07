// [STORE REMOVED] Backend store service deleted — this Zustand store now returns disabled defaults
import { create } from "zustand";
// import { ENABLE_LANGBUILDER_STORE } from "@/customization/feature-flags";
// import { checkHasApiKey, checkHasStore } from "../controllers/API";
import type { StoreStoreType } from "../types/zustand/store";

export const useStoreStore = create<StoreStoreType>((set) => ({
  hasStore: false,
  validApiKey: false,
  hasApiKey: false,
  loadingApiKey: false,
  checkHasStore: () => {
    // [STORE REMOVED] was: checkHasStore().then(...)
    set({ hasStore: false });
  },
  updateValidApiKey: (validApiKey) => set(() => ({ validApiKey: validApiKey })),
  updateLoadingApiKey: (loadingApiKey) =>
    set(() => ({ loadingApiKey: loadingApiKey })),
  updateHasApiKey: (hasApiKey) => set(() => ({ hasApiKey: hasApiKey })),
  fetchApiData: async () => {
    // [STORE REMOVED] was: checkHasApiKey().then(...)
    set({ loadingApiKey: false, validApiKey: false, hasApiKey: false });
  },
}));
