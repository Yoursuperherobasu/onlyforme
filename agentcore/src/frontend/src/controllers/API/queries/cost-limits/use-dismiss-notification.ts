import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DismissParams {
  notification_id: string;
}

export const useDismissCostNotification: useMutationFunctionType<
  undefined,
  DismissParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function dismissNotification({
    notification_id,
  }: DismissParams): Promise<any> {
    const res = await api.post(
      `${getURL("COST_LIMITS")}/notifications/${notification_id}/dismiss`,
    );
    return res.data;
  }

  const mutation: UseMutationResult<any, any, DismissParams> = mutate(
    ["useDismissCostNotification"],
    dismissNotification,
    options,
  );

  return mutation;
};
