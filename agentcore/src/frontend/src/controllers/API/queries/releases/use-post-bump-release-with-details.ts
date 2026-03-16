import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { ReleaseRecord } from "./use-get-releases";

export type ReleaseDetailInputPayload = {
  section_no?: number;
  section_title?: string;
  module?: string;
  sub_module?: string;
  feature_capability: string;
  description_details?: string;
};

export type ReleaseBumpWithDetailsPayload = {
  bump_type: "major" | "minor" | "patch";
  release_notes?: string;
  details_file?: File;
  manual_details?: ReleaseDetailInputPayload[];
};

export const usePostBumpReleaseWithDetails = (options?: any) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const bumpReleaseWithDetailsFn = async (
    payload: ReleaseBumpWithDetailsPayload,
  ): Promise<ReleaseRecord> => {
    const body = new FormData();
    body.append("bump_type", payload.bump_type);

    if (payload.release_notes?.trim()) {
      body.append("release_notes", payload.release_notes.trim());
    }

    if (payload.details_file) {
      body.append("details_file", payload.details_file);
    } else {
      body.append("details_json", JSON.stringify(payload.manual_details ?? []));
    }

    const res = await api.post(`${getURL("RELEASES")}/bump-with-details`, body);
    return res.data;
  };

  return mutate(["usePostBumpReleaseWithDetails"], bumpReleaseWithDetailsFn, {
    ...options,
    onSettled: (...args) => {
      queryClient.invalidateQueries({ queryKey: ["useGetCurrentRelease"] });
      queryClient.invalidateQueries({ queryKey: ["useGetReleases"] });
      options?.onSettled?.(...args);
    },
  }) as UseMutationResult<ReleaseRecord, any, ReleaseBumpWithDetailsPayload>;
};
